class Parser:
    def __init__(self, lexer):
        self.lexer = lexer
        self.current = self.lexer.read_token()
        self._in_if_chain = False

    def _eat(self, type=None, value=None):
        tok = self.current
        if type is not None and tok.type != type:
            raise Exception(
                f"Syntax Error at {tok.line}:{tok.col}: "
                f"Expected {type}, got {tok.type}('{tok.value}')"
            )
        if value is not None and tok.value != value:
            raise Exception(
                f"Syntax Error at {tok.line}:{tok.col}: "
                f"Expected '{value}', got '{tok.value}'"
            )
        self.current = self.lexer.read_token()
        return tok

    def _skip_newlines(self):
        while self.current.type == "NEWLINE":
            self._eat("NEWLINE")

    # ------------------------------------------------------------
    # Program
    # ------------------------------------------------------------

    def parse_program(self):
        statements = []
        self._skip_newlines()

        while self.current.type != "EOF":
            stmt = self.parse_statement()

            while self.current.type == "OPERATOR" and self.current.value == ";":
                self._eat("OPERATOR", ";")

            statements.append(stmt)
            self._skip_newlines()

        return ("program", statements)

    # ------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------

    def parse_statement(self):
        if self.current.type == "KEYWORD":
            kw = self.current.value
            if kw == "extern":
                return self.parse_extern()
            if kw == "def":
                return self.parse_function_def()
            if kw == "return":
                return self.parse_return()
            if kw == "if":
                return self.parse_if()
            if kw == "elif":
                return self.parse_elif()
            if kw == "else":
                return self.parse_else()
            if kw == "while":
                return self.parse_while()
            if kw == "repeat":
                return self.parse_repeat()

        return self.parse_expression()

    # ------------------------------------------------------------
    # extern def
    # ------------------------------------------------------------

    def parse_extern(self):
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

    # ------------------------------------------------------------
    # Function definition
    # ------------------------------------------------------------

    def parse_function_def(self):
        self._eat("KEYWORD", "def")
        name = self._eat("IDENTIFIER").value

        self._eat("OPERATOR", "(")
        params = self.parse_params(is_extern=False)
        self._eat("OPERATOR", ")")

        ret_type = "void"
        if self.current.type == "OPERATOR" and self.current.value == "->":
            self._eat("OPERATOR", "->")
            ret_type = self._eat("KEYWORD").value

        self._eat("OPERATOR", ":")
        self._skip_newlines()

        self._eat("INDENT")
        body = []
        while self.current.type not in {"DEDENT", "EOF"}:
            body.append(self.parse_statement())
            self._skip_newlines()
        self._eat("DEDENT")

        return ("function", name, params, ret_type, body)

    # ------------------------------------------------------------
    # if / elif / else
    # ------------------------------------------------------------

    def parse_if(self):
        self._in_if_chain = True

        self._eat("KEYWORD", "if")
        cond = self.parse_expression()
        self._eat("OPERATOR", ":")
        self._skip_newlines()

        self._eat("INDENT")
        body = []
        while self.current.type not in {"DEDENT", "EOF"}:
            body.append(self.parse_statement())
            self._skip_newlines()
        self._eat("DEDENT")

        elifs = []
        else_body = None

        while self.current.type == "KEYWORD" and self.current.value == "elif":
            elifs.append(self.parse_elif())

        if self.current.type == "KEYWORD" and self.current.value == "else":
            else_body = self.parse_else()

        self._in_if_chain = False
        return ("if", cond, body, elifs, else_body)

    def parse_elif(self):
        if not self._in_if_chain:
            raise Exception(
                f"Dangling 'elif' at {self.current.line}:{self.current.col}"
            )

        self._eat("KEYWORD", "elif")
        cond = self.parse_expression()
        self._eat("OPERATOR", ":")
        self._skip_newlines()

        self._eat("INDENT")
        body = []
        while self.current.type not in {"DEDENT", "EOF"}:
            body.append(self.parse_statement())
            self._skip_newlines()
        self._eat("DEDENT")

        return ("elif", cond, body)

    def parse_else(self):
        if not self._in_if_chain:
            raise Exception(
                f"Dangling 'else' at {self.current.line}:{self.current.col}"
            )

        self._eat("KEYWORD", "else")
        self._eat("OPERATOR", ":")
        self._skip_newlines()

        self._eat("INDENT")
        body = []
        while self.current.type not in {"DEDENT", "EOF"}:
            body.append(self.parse_statement())
            self._skip_newlines()
        self._eat("DEDENT")

        return ("else", body)

    # ------------------------------------------------------------
    # while loop
    # ------------------------------------------------------------

    def parse_while(self):
        self._eat("KEYWORD", "while")
        cond = self.parse_expression()
        self._eat("OPERATOR", ":")
        self._skip_newlines()

        self._eat("INDENT")
        body = []
        while self.current.type not in {"DEDENT", "EOF"}:
            body.append(self.parse_statement())
            self._skip_newlines()
        self._eat("DEDENT")

        return ("while", cond, body)

    # ------------------------------------------------------------
    # repeat loops
    # ------------------------------------------------------------

    def parse_repeat(self):
        self._eat("KEYWORD", "repeat")

        count_expr = self.parse_expression()

        if self.current.type == "OPERATOR" and self.current.value == ",":
            self._eat("OPERATOR", ",")
            counter_name = self._eat("IDENTIFIER").value
            self._eat("OPERATOR", ":")
            self._skip_newlines()

            self._eat("INDENT")
            body = []
            while self.current.type not in {"DEDENT", "EOF"}:
                body.append(self.parse_statement())
                self._skip_newlines()
            self._eat("DEDENT")

            return ("repeat_counter", count_expr, counter_name, body)

        self._eat("OPERATOR", ":")
        self._skip_newlines()

        self._eat("INDENT")
        body = []
        while self.current.type not in {"DEDENT", "EOF"}:
            body.append(self.parse_statement())
            self._skip_newlines()
        self._eat("DEDENT")

        return ("repeat", count_expr, body)

    # ------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------

    def parse_params(self, is_extern=False):
        params = []
        while not (self.current.type == "OPERATOR" and self.current.value == ")"):

            if is_extern and self.current.type == "OPERATOR" and self.current.value == "...":
                self._eat("OPERATOR", "...")
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

    # ------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------

    def parse_expression(self):
        if self.current.type == "KEYWORD" and self.current.value in {
            "int", "float", "double", "big", "str", "arr", "list"
        }:
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
        while self.current.type == "OPERATOR" and self.current.value in {
            "==", "!=", "<", ">", "<=", ">="
        }:
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

    # ------------------------------------------------------------
    # Postfix (calls)
    # ------------------------------------------------------------

    def parse_postfix(self):
        node = self.parse_primary()

        while True:
            if self.current.type == "OPERATOR" and self.current.value == "(":
                self._eat("OPERATOR", "(")
                args = []
                if not (self.current.type == "OPERATOR" and self.current.value == ")"):
                    while True:
                        args.append(self.parse_expression())
                        if self.current.type == "OPERATOR" and self.current.value == ",":
                            self._eat("OPERATOR", ",")
                        else:
                            break
                self._eat("OPERATOR", ")")
                node = ("call", node, args)
                continue
            break

        return node

    # ------------------------------------------------------------
    # Primary
    # ------------------------------------------------------------

    def parse_primary(self):
        tok = self.current

        if tok.type == "NUMBER_INT":
            self._eat()
            return ("literal", "int", tok.value)

        if tok.type == "NUMBER_FLOAT":
            self._eat()
            return ("literal", "double", tok.value)

        if tok.type in {"STRING", "RAW_STRING", "BYTE_STRING", "FSTRING"}:
            self._eat()
            return ("literal", "str", tok.value)

        if tok.type == "IDENTIFIER":
            self._eat()
            return ("id", tok.value)

        if tok.type == "OPERATOR" and tok.value == "(":
            self._eat("OPERATOR", "(")
            expr = self.parse_expression()
            self._eat("OPERATOR", ")")
            return expr

        raise Exception(
            f"Unexpected token {tok.type}('{tok.value}') at {tok.line}:{tok.col}"
        )

    # ------------------------------------------------------------
    # return
    # ------------------------------------------------------------

    def parse_return(self):
        self._eat("KEYWORD", "return")
        if self.current.type in {"NEWLINE", "EOF"}:
            return ("return", None)
        return ("return", self.parse_expression())
