class Parser:
    def __init__(self, lexer):
        self.lexer = lexer
        self.current = self.lexer.read_token()

    def _eat(self, type=None, value=None):
        tok = self.current
        if type is not None and tok.type != type:
            raise Exception(f"Syntax Error at {tok.line}:{tok.col}: Expected {type}, got {tok.type}")
        if value is not None and tok.value != value:
            raise Exception(f"Syntax Error at {tok.line}:{tok.col}: Expected '{value}', got '{tok.value}'")
        self.current = self.lexer.read_token()
        return tok

    def parse_program(self):
        """Entry point: Parses a sequence of statements until EOF."""
        statements = []
        while self.current.type != "EOF":
            # Skip empty lines/newlines if the lexer produces them
            if self.current.type == "OPERATOR" and self.current.value == ";":
                self._eat()
                continue
            statements.append(self.parse_statement())
        return ("program", statements)

    def parse_statement(self):
        """Distinguishes between keywords (def, extern, if) and expressions."""
        if self.current.type == "KEYWORD":
            if self.current.value == "extern":
                return self.parse_extern()
            if self.current.value == "def":
                return self.parse_function_def()
            if self.current.value == "return":
                return self.parse_return()
            
        # Default to expression statement (assignments, calls, etc.)
        return self.parse_expression()

    def parse_extern(self):
        """extern def name(params) -> type"""
        self._eat("KEYWORD", "extern")
        self._eat("KEYWORD", "def")
        name = self._eat("IDENTIFIER").value
        self._eat("OPERATOR", "(")
        params = self.parse_params(is_extern=True)
        self._eat("OPERATOR", ")")
        
        ret_type = "void"
        if self.current.type == "OPERATOR" and self.current.value == "->":
            self._eat("OPERATOR", "->")
            ret_type = self._eat("KEYWORD").value

        alias = name
        if self.current.type == "KEYWORD" and self.current.value == "as":
            self._eat("KEYWORD", "as")
            alias = self._eat("IDENTIFIER").value
        
        return ("extern", name, params, ret_type, alias)

    def parse_params(self, is_extern=False):
        """Parses parameter lists like (a: int, b: str)"""
        params = []
        while self.current.type != "OPERATOR" or self.current.value != ")":
            # Handle variadic C-functions like printf(fmt, ...)
            if is_extern and self.current.type == "OPERATOR" and self.current.value == ".":
                for _ in range(3): self._eat("OPERATOR", ".")
                params.append(("variadic", "..."))
                break
                
            p_name = self._eat("IDENTIFIER").value
            self._eat("OPERATOR", ":")
            p_type = self._eat("KEYWORD").value
            params.append((p_name, p_type))
            
            if self.current.type == "OPERATOR" and self.current.value == ",":
                self._eat("OPERATOR", ",")
            else:
                break
        return params

    def parse_expression(self):
        """Expression with assignment support (right-associative)."""
        # Type-based declaration: int x = 5
        if self.current.type == "KEYWORD" and self.current.value in {"int", "float", "double", "big", "str", "arr", "list"}:
            v_type = self._eat("KEYWORD").value
            v_name = self._eat("IDENTIFIER").value
            v_value = None
            if self.current.type == "OPERATOR" and self.current.value == "=":
                self._eat("OPERATOR", "=")
                v_value = self.parse_expression()
            return ("decl", v_type, v_name, v_value)

        return self.parse_assignment()

    def parse_assignment(self):
        left = self.parse_compare()
        if self.current.type == "OPERATOR" and self.current.value == "=":
            self._eat("OPERATOR", "=")
            right = self.parse_assignment()
            return ("assign", left, right)
        return left

    def parse_compare(self):
        node = self.parse_add()
        while self.current.type == "OPERATOR" and self.current.value in {"==", "!=", "<", ">", "<=", ">="}:
            op = self._eat().value
            right = self.parse_add()
            node = ("binop", op, node, right)
        return node

    def parse_add(self):
        node = self.parse_mul()
        while self.current.type == "OPERATOR" and self.current.value in {"+", "-"}:
            op = self._eat().value
            right = self.parse_mul()
            node = ("binop", op, node, right)
        return node

    def parse_mul(self):
        node = self.parse_unary()
        while self.current.type == "OPERATOR" and self.current.value in {"*", "/", "%"}:
            op = self._eat().value
            right = self.parse_unary()
            node = ("binop", op, node, right)
        return node

    def parse_unary(self):
        if self.current.type == "OPERATOR" and self.current.value in {"-", "!", "*"}:
            op = self._eat().value
            return ("unary", op, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()
        
        # Handle function calls: name(args)
        if self.current.type == "OPERATOR" and self.current.value == "(":
            self._eat("OPERATOR", "(")
            args = []
            if not (self.current.type == "OPERATOR" and self.current.value == ")"):
                while True:
                    args.append(self.parse_expression())
                    if self.current.type == "OPERATOR" and self.current.value == ",":
                        self._eat(",")
                    else: break
            self._eat("OPERATOR", ")")
            return ("call", node, args)
            
        return node

    def parse_primary(self):
        token = self.current
        if token.type == "NUMBER_INT":
            self._eat()
            return ("literal", "int", token.value)
        if token.type == "NUMBER_FLOAT":
            self._eat()
            return ("literal", "double", token.value)
        if token.type == "STRING":
            self._eat()
            return ("literal", "str", token.value)
        if token.type == "IDENTIFIER":
            self._eat()
            return ("id", token.value)
        if token.type == "OPERATOR" and token.value == "(":
            self._eat("OPERATOR", "(")
            expr = self.parse_expression()
            self._eat("OPERATOR", ")")
            return expr
        
        raise Exception(f"Unexpected token {token}")

    def parse_return(self):
        self._eat("KEYWORD", "return")
        val = None
        if self.current.type != "EOF": # Simple check for line end
             val = self.parse_expression()
        return ("return", val)
