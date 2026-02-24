from llvmlite import ir, binding

class ChitonCompiler:
    # init
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
        self.structs = {}
        
        self.type_map = {
            "int": ir.IntType(32),
            "float": ir.FloatType(),
            "double": ir.DoubleType(),
            "big": ir.IntType(128),
            "str": ir.PointerType(ir.IntType(8)),
            "void": ir.VoidType(),
            "bool": ir.IntType(1)
        }

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

    def enter_scope(self):
        self.scope_stack.append(self.symbols.copy())

    def exit_scope(self):
        self.symbols = self.scope_stack.pop()

    # mapping
    def _gen_node(self, node):
        node_type = node[0]
        if node_type == "extern": return self._gen_extern(node)
        elif node_type == "decl": return self._gen_decl(node)
        elif node_type == "assign": return self._gen_assign(node)
        elif node_type == "literal": return self._gen_literal(node)
        elif node_type == "id": return self._gen_id(node)
        elif node_type == "class": return self._gen_class(node)
        elif node_type == "def": return self._gen_function_def(node)
        elif node_type == "binop": return self._gen_binop(node)
        elif node_type == "call": return self._gen_call(node)
        elif node_type == "return": return self._gen_return(node)
        elif node_type == "member_access": return self._gen_member_access(node)
        elif node_type == "while": return self._gen_while(node)
        elif node_type == "repeat": return self._gen_repeat(node)

    # C fuction calls
    def _gen_extern(self, node):
        name = node[1]
        params = node[2]
        ret_type_name = node[3]
        
        llvm_params = []
        for p in params:
            if p[0] == "variadic": continue
            llvm_params.append(self.type_map[p[1]])
            
        is_vararg = any(p[0] == "variadic" for p in params)
        fnty = ir.FunctionType(self.type_map[ret_type_name], llvm_params, var_arg=is_vararg)
        func = ir.Function(self.module, fnty, name=name)
        func.linkage = "external"
        self.symbols[name] = func
        return func

    # map classes to structs with methods
    def _gen_class(self, node):
        class_name = node[1]
        fields = node[2]
        
        llvm_fields = [self.type_map[f[1]] for f in fields]
        struct_ty = self.module.context.get_identified_type(f"struct.{class_name}")
        struct_ty.set_body(*llvm_fields)
        
        self.structs[class_name] = {
            "type": struct_ty,
            "fields": {f[0]: i for i, f in enumerate(fields)}
        }
        self.type_map[class_name] = struct_ty.as_pointer()

    def _gen_decl(self, node):
        v_type_name = node[1]
        v_name = node[2]
        v_expr = node[3]
        
        llvm_ty = self.type_map[v_type_name]
        ptr = self.builder.alloca(llvm_ty, name=v_name)
        self.symbols[v_name] = ptr
        
        if v_expr:
            val = self._gen_node(v_expr)
            self.builder.store(val, ptr)
        return ptr

    def _gen_assign(self, node):
        target_node = node[1]
        value_node = node[2]
        val = self._gen_node(value_node)
        
        if target_node[0] == "id":
            ptr = self.symbols[target_node[1]]
            self.builder.store(val, ptr)
        elif target_node[0] == "member_access":
            ptr = self._gen_member_addr(target_node)
            self.builder.store(val, ptr)
        return val

    def _gen_literal(self, node):
        val_type = node[1]
        value = node[2]
        if val_type == "int":
            return ir.Constant(self.type_map["int"], int(value))
        elif val_type == "double":
            return ir.Constant(self.type_map["double"], float(value))
        elif val_type == "str":
            str_val = value + "\0"
            const_str = ir.Constant(ir.ArrayType(ir.IntType(8), len(str_val)), bytearray(str_val.encode("utf8")))
            global_str = ir.GlobalVariable(self.module, const_str.type, name=f"str_{id(value)}")
            global_str.initializer = const_str
            global_str.linkage = "internal"
            return self.builder.bitcast(global_str, self.type_map["str"])

    def _gen_id(self, node):
        name = node[1]
        ptr = self.symbols.get(name)
        if isinstance(ptr, ir.Function): return ptr
        return self.builder.load(ptr, name)

    def _gen_function_def(self, node):
        name = node[1]
        params = node[2]
        ret_type_name = node[3]
        body = node[4]
        
        llvm_params = [self.type_map[p[1]] for p in params]
        fnty = ir.FunctionType(self.type_map[ret_type_name], llvm_params)
        func = ir.Function(self.module, fnty, name=name)
        
        block = func.append_basic_block(name="entry")
        previous_builder = self.builder
        previous_func = self.func
        self.builder = ir.IRBuilder(block)
        self.func = func
        
        self.enter_scope()
        for i, (p_name, p_type) in enumerate(params):
            ptr = self.builder.alloca(self.type_map[p_type], name=p_name)
            self.builder.store(func.args[i], ptr)
            self.symbols[p_name] = ptr
            
        for stmt in body:
            self._gen_node(stmt)
            
        self.exit_scope()
        self.builder = previous_builder
        self.func = previous_func
        return func

    def _gen_binop(self, node):
        op = node[1]
        left = self._gen_node(node[2])
        right = self._gen_node(node[3])
        
        if left.type == ir.IntType(128):
            return self._gen_big_binop(op, left, right)
            
        if op == "+": return self.builder.add(left, right)
        if op == "-": return self.builder.sub(left, right)
        if op == "*": return self.builder.mul(left, right)
        if op == "/": return self.builder.sdiv(left, right)
        if op == "==": return self.builder.icmp_signed("==", left, right)
        if op == "<": return self.builder.icmp_signed("<", left, right)
        if op == ">": return self.builder.icmp_signed(">", left, right)

    def _gen_big_binop(self, op, left, right):
        if op == "+": return self.builder.add(left, right)
        if op == "-": return self.builder.sub(left, right)
        if op == "*": return self.builder.mul(left, right)
        if op == "/": return self.builder.sdiv(left, right)
        return self.builder.icmp_signed(op, left, right)

    def _gen_call(self, node):
        callee_node = node[1]
        args_nodes = node[2]
        
        if isinstance(callee_node, str):
            callee = self.symbols[callee_node]
        else:
            callee = self._gen_node(callee_node)
            
        args = [self._gen_node(a) for a in args_nodes]
        return self.builder.call(callee, args)

    def _gen_return(self, node):
        val_node = node[1]
        if val_node:
            val = self._gen_node(val_node)
            return self.builder.ret(val)
        return self.builder.ret_void()

    def _gen_member_addr(self, node):
        obj_node = node[1]
        member_name = node[2]
        
        obj_ptr = self._gen_node(obj_node)
        struct_ty = obj_ptr.type.pointee
        class_name = struct_ty.name.replace("struct.", "")
        field_idx = self.structs[class_name]["fields"][member_name]
        
        return self.builder.gep(obj_ptr, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), field_idx)
        ], name=f"field_{member_name}")

    def _gen_member_access(self, node):
        addr = self._gen_member_addr(node)
        return self.builder.load(addr)

    def _gen_while(self, node):
        cond_node = node[1]
        body_nodes = node[2]

        cond_block = self.func.append_basic_block(name="while_cond")
        body_block = self.func.append_basic_block(name="while_body")
        after_block = self.func.append_basic_block(name="while_after")

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

    def _gen_repeat(self, node):
        count_node = node[1]
        body_nodes = node[2]

        count_val = self._gen_node(count_node)
        iter_ptr = self.builder.alloca(ir.IntType(32), name="repeat_counter")
        self.builder.store(ir.Constant(ir.IntType(32), 0), iter_ptr)

        cond_block = self.func.append_basic_block(name="repeat_cond")
        body_block = self.func.append_basic_block(name="repeat_body")
        after_block = self.func.append_basic_block(name="repeat_after")

        self.builder.branch(cond_block)
        self.builder.position_at_end(cond_block)

        curr_iter = self.builder.load(iter_ptr)
        cond = self.builder.icmp_signed("<", curr_iter, count_val)
        self.builder.cbranch(cond, body_block, after_block)

        self.builder.position_at_end(body_block)
        for stmt in body_nodes:
            self._gen_node(stmt)
        
        new_iter = self.builder.add(curr_iter, ir.Constant(ir.IntType(32), 1))
        self.builder.store(new_iter, iter_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_end(after_block)