def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[str]:

    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # If we're not at the end, look for a better boundary.
        if end < len(text):

            search_area = text[start:end]

            # Prefer paragraph → sentence → word boundary
            split_at = search_area.rfind("\n\n")

            if split_at == -1:
                split_at = search_area.rfind(". ")

            if split_at == -1:
                split_at = search_area.rfind(" ")

            # Only use the boundary if it isn't too close to the start
            if split_at > chunk_size // 2:
                end = start + split_at + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        # Move backwards to create overlap
        next_start = max(0, end - overlap)

        # Avoid starting halfway through a word
        if next_start > 0:
            space = text.find(" ", next_start)

            if space != -1 and space < end:
                next_start = space + 1

        # Safety check: always move forward
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks
