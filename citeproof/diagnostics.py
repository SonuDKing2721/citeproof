"""Extract short, untrusted traceback clues from a Python issue report."""

import ast
import re


_FRAME = re.compile(
    r'^\s*File\s+["\'](?P<path>[^"\']+\.py)["\']\s*,\s*'
    r'line\s+(?P<line>\d+)\s*,\s*in\s+(?P<function>[\w.<>]+)',
    re.MULTILINE,
)
_EXCEPTION = re.compile(
    r'^\s*(?P<kind>[A-Za-z_][\w.]*(?:Error|Exception|Warning|Group|Exit|Interrupt))\s*:\s*'
    r'(?P<message>[^\r\n]*)',
    re.MULTILINE,
)
_CODE_BLOCK = re.compile(r"```(?P<language>[^\r\n`]*)\r?\n(?P<body>.*?)```", re.DOTALL)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _is_test_harness_module(module: str) -> bool:
    markers = {"test", "tests", "testing", "runner", "pytest", "unittest", "mock"}
    parts = [part.casefold() for part in module.split(".") if part]
    return any(
        part in markers or part.startswith("test_") or part.endswith("_test")
        for part in parts
    )


def _expand_module_alias(name: str, aliases: dict[str, str]) -> str:
    base, separator, suffix = name.partition(".")
    canonical = aliases.get(base, base)
    return canonical + (separator + suffix if separator else "")


def extract_reproducer_api_hints(issue: str, *, max_symbols: int = 3) -> list[str]:
    """Extract public-looking imported call names from Python examples without executing them.

    Names imported from test harness modules are excluded so a traceback wrapper
    such as ``CliRunner.invoke`` does not outrank the API called by the example.
    Returned identifiers are untrusted search hints, never evidence.
    """
    hints: list[str] = []
    if max_symbols <= 0:
        return hints

    for block in list(_CODE_BLOCK.finditer(issue[:12000]))[:8]:
        language = block.group("language").strip().casefold()
        if language not in {"", "python", "py"}:
            continue
        source = block.group("body")[:5000]
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            continue

        imports: dict[str, tuple[str, str]] = {}
        module_aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if alias.name != "*":
                        imports[alias.asname or alias.name] = (module, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split(".", 1)[0]
                    module_name = alias.name if alias.asname else alias.name.split(".", 1)[0]
                    module_aliases[local_name] = module_name

        instance_modules: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
                continue
            imported = imports.get(value.func.id)
            if not imported:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    instance_modules[target.id] = imported[0]

        decorator_calls: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        decorator_calls.add(id(decorator))

        calls = sorted(
            (node for node in ast.walk(tree) if isinstance(node, ast.Call)),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for call in calls:
            if id(call) in decorator_calls:
                continue
            module = ""
            symbol = ""
            if isinstance(call.func, ast.Name):
                imported = imports.get(call.func.id)
                if imported:
                    module, symbol = imported
            elif isinstance(call.func, ast.Attribute):
                receiver = call.func.value
                receiver_name = _dotted_name(receiver)
                if isinstance(receiver, ast.Name) and receiver.id in instance_modules:
                    module = instance_modules[receiver.id]
                elif isinstance(receiver, ast.Call):
                    constructor_name = _dotted_name(receiver.func)
                    if isinstance(receiver.func, ast.Name) and receiver.func.id in imports:
                        module = imports[receiver.func.id][0]
                    elif constructor_name:
                        constructor_name = _expand_module_alias(constructor_name, module_aliases)
                        module = ".".join(constructor_name.split(".")[:-1])
                elif receiver_name:
                    module = _expand_module_alias(receiver_name, module_aliases)
                    if module == receiver_name and receiver_name not in module_aliases:
                        module = ""
                    if not module and receiver_name in instance_modules:
                        module = instance_modules[receiver_name]
                symbol = call.func.attr
            if not module or _is_test_harness_module(module):
                continue
            if not symbol:
                symbol = call.func.id if isinstance(call.func, ast.Name) else ""
            if symbol.isidentifier() and symbol not in hints:
                hints.append(symbol)
                if len(hints) >= max_symbols:
                    return hints
    return hints


def _short_repository_path(path: str) -> str:
    parts = [part for part in path.replace("\\", "/").split("/") if part and part not in {".", ".."}]
    lowered = [part.casefold() for part in parts]
    marker = next(
        (lowered.index(name) for name in ("site-packages", "dist-packages", "src") if name in lowered),
        None,
    )
    suffix = parts[marker + 1 :] if marker is not None else parts[-2:]
    cleaned = [re.sub(r"[^A-Za-z0-9_.-]", "", part) for part in suffix]
    return "/".join(part for part in cleaned if part)[-140:]


def extract_diagnostic_hints(issue: str, *, max_frames: int = 3) -> list[str]:
    """Return compact exception and deepest-frame hints, never trusted evidence."""
    hints: list[str] = []
    exceptions = list(_EXCEPTION.finditer(issue))[-2:]
    for match in reversed(exceptions):
        kind = match.group("kind")[:80]
        message = match.group("message").strip()[:220]
        hints.append(f"Exception: {kind}: {message}".rstrip())

    frame_limit = max(0, max_frames)
    frame_matches = list(_FRAME.finditer(issue))
    frames = frame_matches[-frame_limit:] if frame_limit else []
    for match in reversed(frames):
        path = _short_repository_path(match.group("path"))
        function = match.group("function")[:80]
        try:
            line_number = int(match.group("line"))
        except ValueError:
            continue
        if path and line_number > 0:
            hints.append(f"Traceback frame: {path}:{line_number} in {function}")
    return hints
