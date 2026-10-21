# Inglês Real

App **desktop** de inglês americano da vida real (EUA): reduções (`gonna`, `wanna`, `whatcha doin'`), gírias, idioms e phrasal verbs. Interface em português; as frases ouvidas são em inglês, com a voz neural **Jenny** (`en-US-JennyNeural`).

Isto **não** é o TrilhaPy e **não** ensina Python.

## Rodar no computador

Precisa de Python 3.10+ e Tkinter (`python3-tk` no Ubuntu/Debian).

```bash
git clone https://github.com/alavancagem940-web/ingles-real.git
cd ingles-real
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Na primeira abertura aparece o **Teste de Nivelamento**. O resultado (Iniciante / Intermediário / Avançado) destrava os módulos daquele patamar. Fechar e reabrir continua de onde você parou: o progresso fica em `user_progress.json` (arquivo local, sem login e sem nuvem).

Em todo exercício e em toda frase há o botão **Ouvir Pronúncia Nativa** (edge-tts + pygame, ritmo `-10%`, pitch `-5Hz`).

## Acompanhar no celular

O Python desktop **não instala no iPhone**. A versão de celular é um PWA companheiro, também na conta [alavancagem940-web](https://github.com/alavancagem940-web), em repositório separado — **não use o TrilhaPy**.

Quando o GitHub Pages do PWA estiver no ar, o endereço será:

`https://alavancagem940-web.github.io/ingles-real-web/`

Até lá, versionamos este desktop aqui para você clonar no PC. No telefone: abra o PWA no Safari ou Chrome → **Adicionar à Tela de Início**.

## O que tem no app

- Teste de nivelamento só na primeira vez (dá para refazer depois, sem apagar XP)
- Trilhas: **Básico**, **Intermediário**, **Avançado**, **Fluência / Expressões**
- Card **Explicação Teórica Prática** antes dos exercícios (regra, cultura, exemplos com tradução)
- XP, módulos concluídos e posição da lição salvos em `user_progress.json`

## Estrutura

| Arquivo | Função |
| --- | --- |
| `main.py` | Entrada |
| `audio_engine.py` | TTS neural (Jenny / Ana) + pygame |
| `database.py` | Persistência local (`user_progress.json`) |
| `lessons.py` | Currículo |
| `ui.py` | Interface CustomTkinter |

```bash
python -m pytest
```

## Licença

Uso pessoal / estudo. Conteúdo didático original; não é material do TrilhaPy.
