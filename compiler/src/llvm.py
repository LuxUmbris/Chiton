from llvmlite import ir, binding

class ChitonCompiler:
    def __init__(self, target_triple=None):
        self.module = ir.Module(name="chiton_module")

        binding.initialize()
        binding.initialize_all_targets()
        binding.initialize_all_asmprinters()

        self.target_triple = target_triple or binding.get_default_triple()
        self.module.triple = self.target_triple

        self.builder = None
        self.func = None
        self.symbols = {}
        self.scope_stack = []

        self.type_map = {
            "int":    ir.IntType(32),
            "float":  ir.FloatType(),
            "double": ir.DoubleType(),
            "big":    ir.IntType(128),
            "str":    ir.PointerType(ir.IntType(8)),
            "void":   ir.VoidType(),
            "bool":   ir.IntType(1),
        }

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _entry_alloca(self, name, llvm_ty):
        entry = self.func.entry_basic_block
        tmp_builder = ir.IRBuilder(entry)
        return tmp_builder.alloca(llvm_ty, name=name)

    def _promote(self, left, right):
        lt = left.type
        rt = right.type

        if lt == rt:
            return left, right, lt

        # int <-> float/double
        if isinstance(lt, ir.IntType) and isinstance(rt, ir.FloatType):
            left = self.builder.sitofp(left, rt)
            return left, right, rt
        if isinstance(rt, ir.IntType) and isinstance(lt, ir.FloatType):
            right = self.builder.sitofp(right, lt)
            return left, right, lt

        if isinstance(lt, ir.IntType) and isinstance(rt, ir.DoubleType):
            left = self.builder.sitofp(left, rt)
            return left, right, rt
        if isinstance(rt, ir.IntType) and isinstance(lt, ir.DoubleType):
            right = self.builder.sitofp(right, lt)
            return left, right, lt

        # float <-> double
        if isinstance(lt, ir.FloatType) and isinstance(rt, ir.DoubleType):
            left = self.builder.fpext(left, rt)
            return left, right, rt
        if isinstance(rt, ir.FloatType) and isinstance(lt, ir.DoubleType):
            right = self.builder.fpext(right, lt)
            return left, right, lt

        # promote smaller ints to 128-bit "big"
        if isinstance(lt, ir.IntType) and lt.width < 128 and isinstance(rt, ir.IntType) and rt.width == 128:
            left = self.builder.sext(left, rt)
            return left, right, rt
        if isinstance(rt, ir.IntType) and rt.width < 128 and isinstance(lt, ir.IntType) and lt.width == 128:
            right = self.builder.sext(right, lt)
            return left, right, lt

        raise Exception(f"Cannot promote types {lt} and {rt}")

    # ------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------

    def compile(self, ast):
        for node in ast[1]:
            self._gen_node(node)
        return str(self.module)

    def generate_object_file(self, filename="output.o"):
        target = binding.Target.from_triple(self.target_triple)
        target_machine = target.create_target_machine()
        self.module.data_layout = target_machine.target_data

        llvm_ir = str(self.module)
        mod = binding.parse_assembly(llvm_ir)
        mod.verify()

        with open(filename, "wb") as f:
            f.write(target_machine.emit_object(mod))

    # ------------------------------------------------------------
    # Scope
    # ------------------------------------------------------------

    def enter_scope(self):
        self.scope_stack.append(self.symbols.copy())

    def exit_scope(self):
        self.symbols = self.scope_stack.pop()

    # ------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------

    def _gen_node(self, node):
        kind = node[0]

        if kind == "extern":          return self._gen_extern(node)
        if kind == "function":        return self._gen_function(node)
        if kind == "decl":            return self._gen_decl(node)
        if kind == "assign":          return self._gen_assign(node)
        if kind == "literal":         return self._gen_literal(node)
        if kind == "id":              return self._gen_id(node)
        if kind == "binop":           return self._gen_binop(node)
        if kind == "call":            return self._gen_call(node)
        if kind == "return":          return self._gen_return(node)
        if kind == "if":              return self._gen_if(node)
        if kind == "while":           return self._gen_while(node)
        if kind == "repeat":          return self._gen_repeat(node)
        if kind == "repeat_counter":  return self._gen_repeat_counter(node)

        raise Exception(f"Unknown AST node kind: {kind}")

    # ------------------------------------------------------------
    # extern
    # ------------------------------------------------------------

    def _gen_extern(self, node):
        name   = node[1]
        params = node[2]
        ret_ty = node[3]
        alias  = node[4]

        llvm_params = []
        for p in params:
            if p[0] == "variadic":
                continue
            llvm_params.append(self.type_map[p[1]])

        is_vararg = any(p[0] == "variadic" for p in params)
        fnty = ir.FunctionType(self.type_map[ret_ty], llvm_params, var_arg=is_vararg)
        func = ir.Function(self.module, fnty, name=name)
        func.linkage = "external"

        self.symbols[alias] = func
        return func

    # ------------------------------------------------------------
    # function
    # ------------------------------------------------------------

    def _gen_function(self, node):
        name   = node[1]
        params = node[2]
        ret_ty = node[3]
        body   = node[4]

        llvm_param_tys = [self.type_map[p[1]] for p in params]
        fnty = ir.FunctionType(self.type_map[ret_ty], llvm_param_tys)
        func = ir.Function(self.module, fnty, name=name)

        entry_block = func.append_basic_block("entry")
        prev_builder = self.builder
        prev_func = self.func

        self.builder = ir.IRBuilder(entry_block)
        self.func = func
        self.enter_scope()

        for i, (p_name, p_type) in enumerate(params):
            ptr = self._entry_alloca(p_name, self.type_map[p_type])
            self.builder.store(func.args[i], ptr)
            self.symbols[p_name] = ptr

        for stmt in body:
            self._gen_node(stmt)

        if not self.builder.block.is_terminated:
            if ret_ty == "void":
                self.builder.ret_void()
            else:
                zero = ir.Constant(self.type_map[ret_ty], 0)
                self.builder.ret(zero)

        self.exit_scope()
        self.builder = prev_builder
        self.func = prev_func
        return func

    # ------------------------------------------------------------
    # decl / assign
    # ------------------------------------------------------------

    def _gen_decl(self, node):
        v_type = node[1]
        v_name = node[2]
        v_expr = node[3]

        llvm_ty = self.type_map[v_type]
        ptr = self._entry_alloca(v_name, llvm_ty)
        self.symbols[v_name] = ptr

        if v_expr is not None:
            val = self._gen_node(v_expr)
            self.builder.store(val, ptr)

        return ptr

    def _gen_assign(self, node):
        target = node[1]
        value_node = node[2]
        val = self._gen_node(value_node)

        if target[0] == "id":
            name = target[1]
            ptr = self.symbols[name]
            self.builder.store(val, ptr)
            return val

        raise Exception("Unsupported assignment target")

    # ------------------------------------------------------------
    # literals / id
    # ------------------------------------------------------------

    def _gen_literal(self, node):
        t = node[1]
        v = node[2]

        if t == "int":
            return ir.Constant(self.type_map["int"], int(v))
        if t == "double":
            return ir.Constant(self.type_map["double"], float(v))
        if t == "str":
            s = v + "\0"
            const = ir.Constant(ir.ArrayType(ir.IntType(8), len(s)), bytearray(s.encode("utf8")))
            gv = ir.GlobalVariable(self.module, const.type, name=f"str_{id(v)}")
            gv.initializer = const
            gv.linkage = "internal"
            return self.builder.bitcast(gv, self.type_map["str"])

        raise Exception(f"Unknown literal type: {t}")

    def _gen_id(self, node):
        name = node[1]
        sym = self.symbols.get(name)

        if isinstance(sym, ir.Function):
            return sym

        return self.builder.load(sym)

    # ------------------------------------------------------------
    # binop
    # ------------------------------------------------------------

    def _gen_binop(self, node):
        op = node[1]
        left = self._gen_node(node[2])
        right = self._gen_node(node[3])

        left, right, final_ty = self._promote(left, right)

        is_float = isinstance(final_ty, (ir.FloatType, ir.DoubleType))

        if op in {"+", "-", "*", "/"}:
            if is_float:
                if op == "+": return self.builder.fadd(left, right)
                if op == "-": return self.builder.fsub(left, right)
                if op == "*": return self.builder.fmul(left, right)
                if op == "/": return self.builder.fdiv(left, right)
            else:
                if op == "+": return self.builder.add(left, right)
                if op == "-": return self.builder.sub(left, right)
                if op == "*": return self.builder.mul(left, right)
                if op == "/": return self.builder.sdiv(left, right)

        if op in {"==", "!=", "<", ">", "<=", ">="}:
            if is_float:
                cmp_map = {
                    "==": "oeq",
                    "!=": "one",
                    "<":  "olt",
                    ">":  "ogt",
                    "<=": "ole",
                    ">=": "oge",
                }
                return self.builder.fcmp_ordered(cmp_map[op], left, right)
            else:
                cmp_map = {
                    "==": "==",
                    "!=": "!=",
                    "<":  "<",
                    ">":  ">",
                    "<=": "<=",
                    ">=": ">=",
                }
                return self.builder.icmp_signed(cmp_map[op], left, right)

        raise Exception(f"Unknown operator: {op}")

    # ------------------------------------------------------------
    # call
    # ------------------------------------------------------------

    def _gen_call(self, node):
        callee_node = node[1]
        args_nodes = node[2]

        if callee_node[0] == "id":
            fn = self.symbols[callee_node[1]]
        else:
            fn = self._gen_node(callee_node)

        args = [self._gen_node(a) for a in args_nodes]
        return self.builder.call(fn, args)

    # ------------------------------------------------------------
    # return
    # ------------------------------------------------------------

    def _gen_return(self, node):
        expr = node[1]
        if expr is None:
            return self.builder.ret_void()
        val = self._gen_node(expr)
        return self.builder.ret(val)

    # ------------------------------------------------------------
    # if / elif / else
    # ------------------------------------------------------------

    def _gen_if(self, node):
        cond_node   = node[1]
        then_body   = node[2]
        elif_nodes  = node[3]
        else_body   = node[4]

        after_block = self.func.append_basic_block("if_after")

        def gen_branch(cond_node, body_nodes, next_block):
            cond_val = self._gen_node(cond_node)
            then_block = self.func.append_basic_block("if_then")
            self.builder.cbranch(cond_val, then_block, next_block)

            self.builder.position_at_end(then_block)
            for stmt in body_nodes:
                self._gen_node(stmt)
            if not self.builder.block.is_terminated:
                self.builder.branch(after_block)

        # first if
        next_block = self.func.append_basic_block("if_next")
        gen_branch(cond_node, then_body, next_block)

        # chain of elif
        self.builder.position_at_end(next_block)
        for i, elif_node in enumerate(elif_nodes):
            cond = elif_node[1]
            body = elif_node[2]
            next_block = self.func.append_basic_block(f"elif_next_{i}")
            gen_branch(cond, body, next_block)
            self.builder.position_at_end(next_block)

        # else
        if else_body is not None:
            else_block = self.func.append_basic_block("else_body")
            self.builder.branch(else_block)
            self.builder.position_at_end(else_block)
            for stmt in else_body:
                self._gen_node(stmt)
            if not self.builder.block.is_terminated:
                self.builder.branch(after_block)
        else:
            if not self.builder.block.is_terminated:
                self.builder.branch(after_block)

        self.builder.position_at_end(after_block)

    # ------------------------------------------------------------
    # while
    # ------------------------------------------------------------

    def _gen_while(self, node):
        cond_node = node[1]
        body_nodes = node[2]

        cond_block  = self.func.append_basic_block("while_cond")
        body_block  = self.func.append_basic_block("while_body")
        after_block = self.func.append_basic_block("while_after")

        self.builder.branch(cond_block)
        self.builder.position_at_end(cond_block)

        cond_val = self._gen_node(cond_node)
        self.builder.cbranch(cond_val, body_block, after_block)

        self.builder.position_at_end(body_block)
        for stmt in body_nodes:
            self._gen_node(stmt)
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_block)

        self.builder.position_at_end(after_block)

    # ------------------------------------------------------------
    # repeat n:
    # ------------------------------------------------------------

    def _gen_repeat(self, node):
        count_expr = node[1]
        body_nodes = node[2]

        count_val = self._gen_node(count_expr)
        iter_ptr = self._entry_alloca("repeat_i", ir.IntType(32))
        self.builder.store(ir.Constant(ir.IntType(32), 0), iter_ptr)

        cond_block  = self.func.append_basic_block("repeat_cond")
        body_block  = self.func.append_basic_block("repeat_body")
        after_block = self.func.append_basic_block("repeat_after")

        self.builder.branch(cond_block)
        self.builder.position_at_end(cond_block)

        i_val = self.builder.load(iter_ptr)
        cond = self.builder.icmp_signed("<", i_val, count_val)
        self.builder.cbranch(cond, body_block, after_block)

        self.builder.position_at_end(body_block)
        for stmt in body_nodes:
            self._gen_node(stmt)

        new_i = self.builder.add(i_val, ir.Constant(ir.IntType(32), 1))
        self.builder.store(new_i, iter_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_end(after_block)

    # ------------------------------------------------------------
    # repeat n, i:
    # ------------------------------------------------------------

    def _gen_repeat_counter(self, node):
        count_expr   = node[1]
        counter_name = node[2]
        body_nodes   = node[3]

        count_val = self._gen_node(count_expr)
        iter_ptr = self._entry_alloca(counter_name, ir.IntType(32))
        self.symbols[counter_name] = iter_ptr
        self.builder.store(ir.Constant(ir.IntType(32), 0), iter_ptr)

        cond_block  = self.func.append_basic_block("repeatc_cond")
        body_block  = self.func.append_basic_block("repeatc_body")
        after_block = self.func.append_basic_block("repeatc_after")

        self.builder.branch(cond_block)
        self.builder.position_at_end(cond_block)

        i_val = self.builder.load(iter_ptr)
        cond = self.builder.icmp_signed("<", i_val, count_val)
        self.builder.cbranch(cond, body_block, after_block)

        self.builder.position_at_end(body_block)
        for stmt in body_nodes:
            self._gen_node(stmt)

        new_i = self.builder.add(i_val, ir.Constant(ir.IntType(32), 1))
        self.builder.store(new_i, iter_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_end(after_block)
