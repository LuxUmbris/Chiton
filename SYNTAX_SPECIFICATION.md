# Chiton Language — Syntax Specification
### No internals

This document describes how Chiton code **looks** — not how it is parsed or compiled internally.  
It is intended for users of the language.

---

# 1. File Structure

A Chiton project consists of one or more `.ctn` files.

Files may contain:

- variable declarations
- function definitions
- control flow statements
- expressions

Chiton uses **indentation-based blocks** (Python-style).  
Whitespace is significant.

---

# 2. External Functions (C ABI Imports)

Chiton can import C functions using:

```ctn
extern def NAME(param: type, ...) -> return_type as alias
```

All required native libraries must be listed in `build.toml`:

```toml
[dependencies]
c_deps = ["dependency"]
```

### Example

```ctn
extern def printf(fmt: str, ...) -> int as print

print("Hello %d\n", 42)
```

---

# 3. Function Definitions

## Syntax

```ctn
def name(param: type, param2: type) -> return_type:
    <indented block>
```

### Implicit Return Type

If `-> return_type` is omitted, the return type defaults to `void`.

```ctn
def hello(name: str):
    print("Hello ", name)
```

Equivalent to:

```ctn
def hello(name: str) -> void:
    print("Hello ", name)
```

---

## Return Rules

- If a function has return type `void`, it must not return a value.
- If a function has a non-void return type, all execution paths must return a value.
- Returning a value from a `void` function is a compile-time error.

### Example (Error)

```ctn
def test():
    return 5
```
---

# 4. Variables and Declarations

## Syntax

```ctn
type name
type name = expression
```

## Examples

```ctn
int x
int y = 10
double pi = 3.1415
str msg = "Hello"
bool flag = true
```

Variables must be declared before use.

Assignment uses `=`:

```ctn
x = x + 1
```

---

# 5. Built-in Types

Chiton provides the following built-in types:

| Type    | Description |
|---------|------------|
| `int`    | 64-bit signed integer |
| `big`    | 128-bit signed integer |
| `float`  | 32-bit IEEE 754 floating point |
| `double` | 64-bit IEEE 754 floating point |
| `bool`   | Boolean (`true` / `false`) |
| `str`    | String type |
| `void`   | No value / function return type |

---

# 6. Expressions

Chiton supports:

- arithmetic: `a + b * c`
- comparisons: `x < y`, `x == y`
- unary operators: `-x`, `!flag`
- function calls: `f(1, 2)`
- parentheses: `(a + b) * c`

### Example

```ctn
int z = (x + y) * 2

if a < b:
    print("smaller")
```

---

# 7. If / Elif / Else

## Syntax

```ctn
if condition:
    ...
elif other_condition:
    ...
else:
    ...
```

Conditions must evaluate to `bool`.

## Example

```ctn
if x > 10:
    print("big")
elif x == 10:
    print("equal")
else:
    print("small")
```

---

# 8. While Loops

## Syntax

```ctn
while condition:
    <block>
```

The condition must evaluate to `bool`.

## Example

```ctn
while x < 10:
    print(x)
    x = x + 1
```

---

# 9. Repeat Loops

Chiton provides two repeat forms.

## (1) Repeat N Times

```ctn
repeat n:
    <block>
```

Example:

```ctn
repeat 5:
    print("Hello")
```

## (2) Repeat with Counter

```ctn
repeat n, i:
    <block>
```

Inside the block, `i` counts from `0` to `n - 1`.

Example:

```ctn
repeat 3, i:
    print("Index = ", i)
```

---

# 10. Return Statement

## Syntax

```ctn
return
return expression
```

Rules:

- `return` without expression is valid only in `void` functions.
- `return expression` must match the declared return type.

Examples:

```ctn
return
return x + 1
```

---

# 11. Function Calls

## Syntax

```ctn
name(arg1, arg2, ...)
```

## Examples

```ctn
print("Hello")
add(3, 4)
```

---

# 12. Boolean Literals

Chiton defines two boolean literals:

```ctn
true
false
```

Boolean values are not implicitly converted from integers.  
Only `bool` expressions are allowed in conditional statements.

---

# 13. Comments

Chiton currently defines no comment syntax.  
(Comment support may be added in a future revision.)

---

# End of Syntax Specification
