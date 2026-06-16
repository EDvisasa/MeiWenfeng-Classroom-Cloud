from backend.services.response_pipeline import TagStreamInterceptor

interceptor = TagStreamInterceptor(target_tags=["glossary"])
chunks = [
    {"type": "text", "text": "This is a "},
    {"type": "text", "text": "test. <gloss"},
    {"type": "text", "text": "ary>Quantum Computing</glossary> more "},
    {"type": "text", "text": "text <glossary term=\"Qubit\">A qubit</glossary> end."}
]
output = []
for chunk in chunks:
    for out_chunk in interceptor.process_chunk(chunk):
        output.append(out_chunk)
for out_chunk in interceptor.finish():
    output.append(out_chunk)

print("Output:")
print(output)
print("Intercepted:", interceptor.intercepted_data)
