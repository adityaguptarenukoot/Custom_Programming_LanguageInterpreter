class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value
    def __repr__(self):
        return f"{self.type}:{self.value}"

import re

class Lexer:
    def __init__(self, text):
        self.text = text
        self.tokens = []
        self.keywords = {'if', 'else', 'while', 'print', 'function', 'return', 'and', 'or', 'not', 'create'}
        self.token_specification = [
            ('NUMBER',   r'\d+'),
            ('STRING',   r'"[^"]*"'),
            ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),
            ('ASSIGN',   r'='),
            ('END',      r';'),
            ('OP',       r'[+\-*/%]'),
            ('COMPARE',  r'==|!=|<=|>=|<|>'),
            ('LPAREN',   r'\('),
            ('RPAREN',   r'\)'),
            ('LBRACE',   r'\{'),
            ('RBRACE',   r'\}'),
            ('NEWLINE',  r'\n'),
            ('SKIP',     r'[ \t]+'),
            ('MISMATCH', r'.')
        ]

    def tokenize(self):
        tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in self.token_specification)
        for mo in re.finditer(tok_regex, self.text):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'NUMBER':
                value = int(value)
            elif kind == 'STRING':
                value = value.strip('"')
            elif kind == 'ID' and value in self.keywords:
                kind = value.upper()
            elif kind in ('SKIP', 'NEWLINE'):
                continue
            elif kind == 'MISMATCH':
                raise SyntaxError(f"Unexpected character {value}")
            self.tokens.append(Token(kind, value))
        self.tokens.append(Token('EOF', ''))
        return self.tokens

class ReturnValue(Exception):
    def __init__(self, value=None):
        self.value = value

class Interpreter:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.env = {}
        self.declared_vars = set()
        self.functions = {}

    def consume(self, expected_type=None):
        token = self.tokens[self.pos]
        if expected_type and token.type != expected_type:
            raise SyntaxError(f"Expected {expected_type}, got {token.type}")
        self.pos += 1
        return token

    def current(self):
        return self.tokens[self.pos]

    def peek(self):
        return self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else Token('EOF', '')

    def parse(self):
        while self.current().type != 'EOF':
            self.statement()

    def statement(self):
        curr = self.current()
        if curr.type == 'CREATE':
            self.declaration()
        elif curr.type == 'ID' and self.peek().type == 'ASSIGN':
            self.assignment()
        elif curr.type == 'ID' and self.peek().type == 'LPAREN':
            self.function_call()
            self.consume('END')
        elif curr.type == 'PRINT':
            self.consume('PRINT')
            val = self.expr()
            print(val)
            self.consume('END')
        elif curr.type == 'IF':
            self.if_statement()
        elif curr.type == 'WHILE':
            self.while_statement()
        elif curr.type == 'FUNCTION':
            self.function_definition()
        elif curr.type == 'RETURN':
            self.consume('RETURN')
            if self.current().type != 'END':
                value = self.expr()
            else:
                value = None
            self.consume('END')
            raise ReturnValue(value)
        else:
            raise SyntaxError(f"Unknown statement at {curr}")

    def declaration(self):
        self.consume('CREATE')
        var = self.consume('ID').value
        if var in self.declared_vars:
            raise Exception(f"Variable '{var}' already declared.")
        self.consume('ASSIGN')
        value = self.expr()
        self.env[var] = value
        self.declared_vars.add(var)
        self.consume('END')

    def assignment(self):
        var = self.consume('ID').value
        if var not in self.declared_vars:
            raise Exception(f"Variable '{var}' not declared. Use 'create' keyword first.")
        self.consume('ASSIGN')
        value = self.expr()
        self.env[var] = value
        self.consume('END')

    def if_statement(self):
        self.consume('IF')
        self.consume('LPAREN')
        condition = self.expr()
        self.consume('RPAREN')
        self.consume('LBRACE')
        true_block = self.collect_block()
        false_block = []
        if self.current().type == 'ELSE':
            self.consume('ELSE')
            self.consume('LBRACE')
            false_block = self.collect_block()
        block = true_block if condition else false_block
        Interpreter(block).execute_with_env(self.env.copy(), self.functions.copy())

    def while_statement(self):
        self.consume('WHILE')
        self.consume('LPAREN')
        condition_tokens = []
        # collect tokens until RPAREN
        while self.current().type != 'RPAREN':
            condition_tokens.append(self.tokens[self.pos])
            self.pos += 1
        self.consume('RPAREN')
        self.consume('LBRACE')
        body = self.collect_block()
        while Interpreter(condition_tokens).evaluate_with_env(self.env.copy()):
            Interpreter(body.copy()).execute_with_env(self.env.copy(), self.functions.copy())

    def function_definition(self):
        self.consume('FUNCTION')
        name = self.consume('ID').value
        self.consume('LPAREN')
        self.consume('RPAREN')
        self.consume('LBRACE')
        body = self.collect_block()
        self.functions[name] = body

    def function_call(self):
        name = self.consume('ID').value
        self.consume('LPAREN')
        self.consume('RPAREN')
        if name not in self.functions:
            raise Exception(f"Function {name} not defined")
        block = self.functions[name]
        try:
            Interpreter(block).execute_with_env(self.env.copy(), self.functions.copy())
        except ReturnValue as rv:
            return rv.value

    def collect_block(self):
        block = []
        while self.current().type != 'RBRACE':
            block.append(self.tokens[self.pos])
            self.pos += 1
        self.consume('RBRACE')
        return block

    def expr(self):
        result = self.compare_expr()
        while self.current().type in ('AND', 'OR'):
            op = self.consume().type
            right = self.compare_expr()
            if op == 'AND':
                result = result and right
            elif op == 'OR':
                result = result or right
        return result

    def compare_expr(self):
        left = self.term()
        while self.current().type == 'COMPARE':
            op = self.consume().value
            right = self.term()
            if op == '==': left = (left == right)
            elif op == '!=': left = (left != right)
            elif op == '<': left = (left < right)
            elif op == '>': left = (left > right)
            elif op == '<=': left = (left <= right)
            elif op == '>=': left = (left >= right)
        return left

    def term(self):
        token = self.current()
        if token.type == 'NUMBER':
            return self.consume('NUMBER').value
        elif token.type == 'STRING':
            return self.consume('STRING').value
        elif token.type == 'ID':
            var_name = self.consume('ID').value
            if var_name not in self.declared_vars:
                raise Exception(f"Variable '{var_name}' not declared. Use 'create' keyword first.")
            return self.env.get(var_name, 0)
        elif token.type == 'LPAREN':
            self.consume('LPAREN')
            val = self.expr()
            self.consume('RPAREN')
            return val
        else:
            raise SyntaxError(f"Unexpected token in term: {token}")

    def evaluate_with_env(self, env):
        self.env = env
        self.pos = 0
        return self.expr()

    def execute_with_env(self, env, functions):
        self.env = env
        self.declared_vars = set(env.keys())
        self.functions = functions
        self.pos = 0
        self.parse()

def repl():
    print("Custom Language REPL with 'create' keyword for variable declaration. Type 'exit;' to quit.")
    env = {}
    declared_vars = set()
    functions = {}
    while True:
        try:
            user_input = ""
            while True:
                line = input(">>> ")
                user_input += line + "\n"
                if line.strip().endswith(';') or line.strip() == 'exit;':
                    break
            if user_input.strip() == "exit;":
                print("Exiting REPL.")
                break

            lexer = Lexer(user_input)
            tokens = lexer.tokenize()
            interpreter = Interpreter(tokens)
            # Set env and functions for persistent state
            interpreter.env = env
            interpreter.declared_vars = declared_vars
            interpreter.functions = functions
            interpreter.parse()
            # Save updated env and functions after execution
            env = interpreter.env
            declared_vars = interpreter.declared_vars
            functions = interpreter.functions

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    repl()
