from pano.decompiler import decompile

with open('sample.txt', "r") as f:
    code = f.read()
    result = decompile(code)
    for i in result['functions']:
        print(i)
