import inspect
from collections import defaultdict

import click


IGNORED_METHODS = {"HEAD", "OPTIONS"}


def route_inventory(app):
    inventory = []
    for rule in app.url_map.iter_rules():
        view = app.view_functions.get(rule.endpoint)
        original_view = inspect.unwrap(view) if view else None
        source_file = inspect.getsourcefile(original_view) if original_view else None
        function_name = getattr(original_view, "__name__", "-") if original_view else "-"
        for method in sorted(set(rule.methods or ()) - IGNORED_METHODS):
            inventory.append(
                {
                    "method": method,
                    "url": rule.rule,
                    "endpoint": rule.endpoint,
                    "file": source_file or "-",
                    "function": function_name,
                }
            )
    return sorted(inventory, key=lambda item: (item["url"], item["method"], item["endpoint"]))


def find_duplicate_routes(app):
    grouped = defaultdict(list)
    for item in route_inventory(app):
        grouped[(item["method"], item["url"])].append(item)
    return {key: items for key, items in grouped.items() if len(items) > 1}


def assert_no_duplicate_routes(app):
    duplicates = find_duplicate_routes(app)
    if not duplicates:
        return
    lines = ["Duplicate route ditemukan:"]
    for (method, url), items in sorted(duplicates.items()):
        for item in items:
            lines.append(
                f"{method} {url} -> {item['endpoint']} | {item['function']} | {item['file']}"
            )
    raise RuntimeError("\n".join(lines))


def register_route_audit_cli(app):
    @app.cli.command("audit-routes")
    def audit_routes_command():
        """Print the route inventory and fail if method/URL duplicates exist."""
        click.echo("METHOD | URL | ENDPOINT | FILE | FUNCTION")
        for item in route_inventory(app):
            click.echo(
                f"{item['method']} | {item['url']} | {item['endpoint']} | "
                f"{item['file']} | {item['function']}"
            )
        duplicates = find_duplicate_routes(app)
        if duplicates:
            raise click.ClickException("Duplicate route ditemukan. Lihat daftar di atas.")
        click.echo("Duplicate route: 0")
