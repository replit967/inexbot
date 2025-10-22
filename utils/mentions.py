import html
def mention(uid: int, username: str | None, full_name: str | None = None) -> str:
    if username:
        return f"@{username}"
    label = full_name or "игрок"
    return f'<a href="tg://user?id={uid}">{html.escape(label, quote=True)}</a>'
