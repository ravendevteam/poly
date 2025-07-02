"""
    Plugin Name: Calculator
    Description: An advanced calculator plugin for Poly.
    Author: mre31
    Version: 2.0
    Last Updated: July 2, 2025

    This plugin is free software and may be copied and used in any way.
"""

import math
import re

SAFE_DICT = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,

    "abs": abs,
    "pow": pow,
    "round": round,
    "sqrt": math.sqrt,

    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,

    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,

    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,

    "ceil": math.ceil,
    "floor": math.floor,

    "degrees": math.degrees,
    "radians": math.radians,

    "factorial": math.factorial,
    "gamma": math.gamma,
}

def calculate(expression):
    """
    A safe, advanced calculator function that evaluates mathematical expressions.
    Returns a tuple: (result, error_message).
    """
    allowed_chars = r"^[a-zA-Z0-9\.\+\-\*\/\(\)\s\^,]+$"
    expression = expression.replace('^', '**')

    if not re.match(allowed_chars, expression.replace('**', '')):
        return None, "Error: Invalid characters in expression."

    try:
        result = eval(expression, {"__builtins__": {}}, SAFE_DICT)
        return result, None
    except ZeroDivisionError:
        return None, "Error: Division by zero."
    except NameError as e:
        return None, f"Error: Unsupported function or constant used. {e}"
    except Exception as e:
        return None, f"Error: {e}"

def show_help(tab):
    """Displays a formatted help message with all available functions and constants."""
    tab.add("--- Calculator Help ---")
    tab.add("Usage: calc <expression>  OR  = <expression>")
    tab.add("Example: calc sqrt(9) * (pi / 2)")
    tab.add("\nAvailable Operators: +, -, *, /, ** (power), ^ (power)")
    
    constants = sorted([k for k, v in SAFE_DICT.items() if isinstance(v, (int, float))])
    functions = sorted([k for k, v in SAFE_DICT.items() if not isinstance(v, (int, float))])

    tab.add("\nConstants:")
    tab.add("  " + ", ".join(constants))
    
    tab.add("\nFunctions:")
    col_width = 12
    cols = 4
    func_lines = []
    for i in range(0, len(functions), cols):
        line = "".join(f"{f:<{col_width}}" for f in functions[i:i+cols])
        func_lines.append("  " + line)
    tab.add("\n".join(func_lines))
    tab.add("-----------------------")


def register_plugin(app_context):
    """
    Registers the 'calc' and '=' commands.
    """
    define_command = app_context["define_command"]

    def calc_command(tab, args, rest):
        if not rest or rest.strip().lower() == 'help':
            show_help(tab)
            return
        
        result, error = calculate(rest)
        if error:
            tab.add(error)
        else:
            tab.add(str(result))

    define_command("calc", calc_command, [])
    define_command("=", calc_command, [])
