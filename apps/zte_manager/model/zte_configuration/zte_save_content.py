def salvar(nome, conteudo):
    with open(nome, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)

    print(f"Salvo em: {nome}")
