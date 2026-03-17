def choose_tool(route):

    if route["type"] == "concept":
        return "rag"

    if route["type"] == "misconception":
        return "rag"

    if route["type"] == "application":

        if route.get("needs_external"):
            return "mcp"

        return "rag"

    return "rag"