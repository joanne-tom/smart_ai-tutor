import wikipedia

def wiki_search(query):

    try:
        summary = wikipedia.summary(query, sentences=3)
        return summary
    except:
        return "No external information found."