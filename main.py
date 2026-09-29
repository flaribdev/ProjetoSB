# This is a sample Python script.

# Press Ctrl+F5 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press F9 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    try:
        resultado = importar_planilha(ARQUIVO)
        for mes, linhas in sorted(resultado.items()):
            print(f"{mes}: {linhas} linhas importadas")
    except Exception as e:
        print(f"ERRO na importação: {e}")
        raise  # mantém o traceback completo para diagnóstico

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
