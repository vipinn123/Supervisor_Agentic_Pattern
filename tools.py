import re
from contextlib import redirect_stdout
from io import StringIO
io_buffer = StringIO()

def execute_code_in_repl(query):

    """Tool for running python code in a REPL."""
    query = query.replace('\\n','\n')
    query = re.sub(r"^(\s|`)*(?i:python)?\s*", "", query)

    query = re.sub(r"(\s|`)*$", "", query)

    try:
        with redirect_stdout(io_buffer):
            exec(query,globals())
        return io_buffer.getvalue()
    except Exception as e:
        print(f"Error: {e}")

