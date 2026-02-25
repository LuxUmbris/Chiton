class Token:
    def __init__(self, type: str, value: str = "", line: int = 0, col: int = 0):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, '{self.value}', line={self.line}, col={self.col})"


class Lexer:
    def __init__(self, text: str, filename: str = "<input>"):
        # Normalize line endings for determinism
        self.text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1

        self.indent_stack = [0]
        self.pending_dedents = 0
        self.at_line_start = True

        # Longest-match operator list
        self.MULTI_OPS = [
            "...", "..",
            "==", "!=", "<=", ">=", "&&", "||", "->",
            "+=", "-=", "*=", "/=", "++", "--"
        ]
        self.MULTI_OPS.sort(key=len, reverse=True)

        # Strict escape sequences
        self.ESCAPES = {
            "n": "\n",
            "t": "\t",
            "r": "\r",
            '"': '"',
            "\\": "\\",
        }

    # ------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------

    def _peek(self, offset: int = 0) -> str:
        index = self.pos + offset
        return self.text[index] if index < len(self.text) else ""

    def _advance(self) -> str:
        if self.pos >= len(self.text):
            return ""
        ch = self.text[self.pos]
        self.pos += 1

        if ch == "\n":
            self.line += 1
            self.col = 1
            self.at_line_start = True
        else:
            self.col += 1

        return ch

    def _advance_n(self, n: int):
        for _ in range(n):
            self._advance()

    # ------------------------------------------------------------
    # Multi-line comments: ## ... ##
    # ------------------------------------------------------------

    def _skip_multiline_comment(self):
        self._advance()  # #
        self._advance()  # #

        while True:
            ch = self._peek()
            if ch == "":
                raise SyntaxError("Unterminated multi-line comment")

            if ch == "#" and self._peek(1) == "#":
                self._advance()
                self._advance()
                return

            self._advance()

    # ------------------------------------------------------------
    # Empty/comment-only line skip
    # ------------------------------------------------------------

    def _skip_empty_or_comment_line(self):
        i = self.pos
        while i < len(self.text) and self.text[i] == " ":
            i += 1

        # Empty line
        if i < len(self.text) and self.text[i] == "\n":
            while self._peek() == " ":
                self._advance()
            self._advance()
            self.at_line_start = True
            return True

        # Single-line comment
        if i < len(self.text) and self.text[i] == "#":
            while self._peek() not in ("\n", ""):
                self._advance()
            if self._peek() == "\n":
                self._advance()
            self.at_line_start = True
            return True

        return False

    # ------------------------------------------------------------
    # Indentation logic
    # ------------------------------------------------------------

    def _handle_indent(self):
        spaces = 0
        while self._peek() == " ":
            self._advance()
            spaces += 1

        if self._peek() == "\t":
            raise SyntaxError("Tabs are not allowed for indentation")

        current = self.indent_stack[-1]

        if spaces == current:
            return None

        if spaces > current:
            self.indent_stack.append(spaces)
            return Token("INDENT", str(spaces), self.line, 1)

        # Dedent chain
        while spaces < self.indent_stack[-1]:
            self.indent_stack.pop()
            self.pending_dedents += 1

        if spaces != self.indent_stack[-1]:
            raise SyntaxError(f"Inconsistent indentation at line {self.line}")

        return None

    # ------------------------------------------------------------
    # Token readers
    # ------------------------------------------------------------

    def _read_identifier_or_keyword(self) -> Token:
        line, col = self.line, self.col
        name = ""

        while self._peek().isalnum() or self._peek() == "_":
            name += self._advance()

        # STRING PREFIX DETECTION (Python-style)
        # Supports: r"", b"", f"", rf"", fr"", br"", rb""
        if self._peek() == '"':
            if all(c in "rbf" for c in name):
                return self._read_string(name)

        KEYWORDS = {
            "if", "else", "elif", "while", "repeat", "return", "pass",
            "extern", "def", "class", "as",
            "int", "float", "double", "big", "bool", "void", "char",
            "str", "arr", "list",
            "true", "false", "none"
        }

        token_type = "KEYWORD" if name in KEYWORDS else "IDENTIFIER"
        return Token(token_type, name, line, col)

    def _read_number(self) -> Token:
        line, col = self.line, self.col
        num = ""

        while self._peek().isdigit():
            num += self._advance()

        if self._peek() == "." and self._peek(1).isdigit():
            num += self._advance()
            while self._peek().isdigit():
                num += self._advance()
            return Token("NUMBER_FLOAT", num, line, col)

        return Token("NUMBER_INT", num, line, col)

    def _read_string(self, prefix: str) -> Token:
        line, col = self.line, self.col

        raw = ("r" in prefix)
        byte = ("b" in prefix)
        fstr = ("f" in prefix)

        self._advance()  # consume opening "

        content = ""

        while True:
            ch = self._peek()
            if ch == "":
                raise SyntaxError("Unterminated string literal")
            if ch == '"':
                self._advance()
                break

            if raw:
                content += self._advance()
                continue

            if ch == "\\":
                self._advance()
                esc = self._advance()
                if esc not in self.ESCAPES:
                    raise SyntaxError(f"Invalid escape sequence '\\{esc}' at line {line}")
                content += self.ESCAPES[esc]
                continue

            if byte:
                if ord(ch) > 127:
                    raise SyntaxError(f"Non-ASCII character in byte string at line {line}")
                content += self._advance()
                continue

            content += self._advance()

        if raw:
            return Token("RAW_STRING", content, line, col)
        if byte:
            return Token("BYTE_STRING", content, line, col)
        if fstr:
            return Token("FSTRING", content, line, col)

        return Token("STRING", content, line, col)

    def _read_operator(self) -> Token:
        line, col = self.line, self.col

        for op in self.MULTI_OPS:
            if self.text.startswith(op, self.pos):
                self._advance_n(len(op))
                return Token("OPERATOR", op, line, col)

        ch = self._advance()
        return Token("OPERATOR", ch, line, col)

    # ------------------------------------------------------------
    # Main token generator
    # ------------------------------------------------------------

    def read_token(self) -> Token:
        if self.pending_dedents > 0:
            self.pending_dedents -= 1
            return Token("DEDENT", "", self.line, self.col)

        if self.at_line_start:
            if self._peek() == "#" and self._peek(1) == "#":
                self._skip_multiline_comment()
                return self.read_token()

            if self._skip_empty_or_comment_line():
                return Token("NEWLINE", "\\n", self.line - 1, 1)

            self.at_line_start = False
            indent_token = self._handle_indent()
            if indent_token:
                return indent_token
            if self.pending_dedents > 0:
                self.pending_dedents -= 1
                return Token("DEDENT", "", self.line, self.col)

        while self._peek().isspace() and self._peek() != "\n":
            self._advance()

        ch = self._peek()

        if ch == "":
            if len(self.indent_stack) > 1:
                self.indent_stack.pop()
                return Token("DEDENT", "", self.line, self.col)
            return Token("EOF", "", self.line, self.col)

        if ch == "\n":
            self._advance()
            self.at_line_start = True
            return Token("NEWLINE", "\\n", self.line - 1, self.col)

        if ch.isalpha() or ch == "_":
            return self._read_identifier_or_keyword()

        if ch.isdigit():
            return self._read_number()

        if ch == '"':
            return self._read_string("")

        if ch in "+-*/%=<>!&|^:.,()[]{};":
            return self._read_operator()

        return Token("ERROR", self._advance(), self.line, self.col)

    # ------------------------------------------------------------
    # Token generator
    # ------------------------------------------------------------

    def tokenize(self):
        while True:
            tok = self.read_token()
            yield tok
            if tok.type == "EOF":
                break
