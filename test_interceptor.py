from backend.services.response_pipeline import TagStreamInterceptor

interceptor = TagStreamInterceptor()
text = "This is a test. <glossary>Quantum Computing</glossary> more text <glossary term=\"Qubit\">A qubit</glossary> end."
output = ""
for char in text:
    for chunk in interceptor.process_chunk(char):
        output += chunk
for chunk in interceptor.finish():
    output += chunk

print("Output:")
print(repr(output))
print("Intercepted:", interceptor.intercepted_data)
