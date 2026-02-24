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
        self.text = text
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1

    def _peek(self, offset: int = 0) -> str:
        index = self.pos + offset
        return self.text[index] if index < len(self.text) else ""

    def _advance(self) -> str:
        if self.pos >= len(self.text): return ""
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _read_identifier_or_keyword(self) -> Token:
        line, col = self.line, self.col
        name = ""
        while self._peek().isalnum() or self._peek() == "_":
            name += self._advance()

        # Chiton Type Keywords & Control Flow
        KEYWORDS = {
            # Control Flow
            "if", "else", "elif", "while", "repeat", "return", "pass", "extern", "def", "class",
            # Primitive Types (C-ABI compatible)
            "int", "float", "double", "big", "bool", "void", "char",
            # Complex Types
            "str", "arr", "list",
            # Constants
            "true", "false", "none"
        }

        token_type = "KEYWORD" if name in KEYWORDS else "IDENTIFIER"
        return Token(token_type, name, line, col)

    def _read_number(self) -> Token:
        line, col = self.line, self.col
        num_str = ""
        
        while self._peek().isdigit():
            num_str += self._advance()
        
        # Check for Floating Point (float/double)
        if self._peek() == "." and self._peek(1).isdigit():
            num_str += self._advance() # consume '.'
            while self._peek().isdigit():
                num_str += self._advance()
            return Token("NUMBER_FLOAT", num_str, line, col)

        return Token("NUMBER_INT", num_str, line, col)

    def _read_string(self) -> Token:
        """Handles double quoted strings for the 'str' type."""
        line, col = self.line, self.col
        self._advance() # consume opening "
        content = ""
        while self._peek() != '"' and self._peek() != "":
            if self._peek() == "\\": # Basic escape support
                content += self._advance()
            content += self._advance()
        self._advance() # consume closing "
        return Token("STRING", content, line, col)

    def _read_operator(self) -> Token:
        line, col = self.line, self.col
        op = self._advance()
        
        # Extended for C-ABI: pointer (*) and member access (.)
        # Also supports Python-like -> for return types
        MULTI_OPS = {"==", "!=", "<=", ">=", "&&", "||", "->", "+=", "-=", "*=", "/=", "++", "--"}

        if (op + self._peek()) in MULTI_OPS:
            op += self._advance()

        return Token("OPERATOR", op, line, col)

    def read_token(self) -> Token:
        # Skip Whitespace
        while self._peek().isspace():
            # Basic Indent check
            if self.col == 1 and self._peek() == " ":
                spaces = 0
                while self._peek() == " ":
                    self._advance()
                    spaces += 1
                if spaces % 4 == 0 and spaces > 0:
                    return Token("INDENT", str(spaces // 4), self.line, 1)
            else:
                self._advance()

        ch = self._peek()
        if ch == "": return Token("EOF", "", self.line, self.col)

        # Token Logic
        if ch.isalpha() or ch == "_": return self._read_identifier_or_keyword()
        if ch.isdigit(): return self._read_number()
        if ch == '"': return self._read_string()
        if ch in "+-*/%=<>!&|^:.,()[]{};": return self._read_operator()

        unknown = self._advance()
        return Token("ERROR", unknown, self.line, self.col)
