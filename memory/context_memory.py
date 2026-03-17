memory_store = {}

def get_context(student_id):
    return memory_store.get(student_id, [])

def store_doubt(student_id, doubt):

    if student_id not in memory_store:
        memory_store[student_id] = []

    memory_store[student_id].append(doubt)

    # keep only last 5
    memory_store[student_id] = memory_store[student_id][-5:]