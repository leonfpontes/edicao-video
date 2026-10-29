#!/usr/bin/env python3
"""Monta biblioteca/3d/ (catálogo + arquivos) a partir da curadoria abaixo.

Uso (da raiz do repositório): pip install cairosvg && python ferramentas/montar_3d.py

Dois tipos de objeto:
- "render": emoji 3D do Microsoft Fluent Emoji (licença MIT), já com volume, luz e sombra. O editor só
  anima (entra com mola, gira no eixo Y, flutua).
- "extrusao": logo plano de ferramenta/marca (Simple Icons, CC0) na cor oficial; o editor cria a espessura,
  a luz e o reflexo. Logos são marcas registradas dos donos: use só quando a fala citar a ferramenta.

Para acrescentar um emoji depois, sem rodar este script: `editor.py biblioteca baixar 3d "Nome em inglês"`.
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "biblioteca" / "3d"
FLUENT = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/"
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@16.30.0/"

# id, pasta no Fluent Emoji, categoria, tags (pt)
RENDERS = [
 # ideias e estratégia
 ("lampada","Light bulb","ideias",["ideia","insight","solução","criatividade"]),
 ("alvo","Bullseye","estrategia",["meta","objetivo","foco","acerto","OKR"]),
 ("bussola","Compass","estrategia",["direção","rumo","estratégia","norte"]),
 ("mapa","World map","estrategia",["roadmap","plano","caminho","jornada"]),
 ("quebra-cabeca","Puzzle piece","estrategia",["encaixe","integração","peça","solução"]),
 ("cerebro","Brain","ideias",["pensar","inteligência","raciocínio","mente"]),
 ("xadrez","Chess pawn","estrategia",["estratégia","jogada","tática"]),
 ("chave","Key","estrategia",["segredo","acesso","chave do sucesso"]),
 ("lupa","Magnifying glass tilted left","analise",["análise","investigar","diagnóstico","detalhe","discovery"]),
 ("engrenagem","Gear","processo",["processo","configuração","operação","engrenagem"]),
 ("ferramentas","Hammer and wrench","processo",["ferramenta","construir","ajuste","conserto"]),
 ("caixa-ferramentas","Toolbox","processo",["kit","ferramentas","recursos"]),
 ("foguete","Rocket","crescimento",["lançamento","crescimento","decolar","startup","escala"]),
 ("escada","Ladder","crescimento",["evolução","degrau","carreira","subir"]),
 ("bandeira-chegada","Chequered flag","crescimento",["chegada","fim","entrega","meta batida"]),
 ("bandeira","Triangular flag","estrategia",["marco","milestone","marcador"]),
 ("obras","Construction","processo",["em construção","obra","andamento","atenção"]),
 ("laboratorio","Test tube","analise",["teste","experimento","hipótese","MVP"]),
 ("bola-cristal","Crystal ball","ideias",["previsão","futuro","tendência"]),
 # dados e dinheiro
 ("grafico-subindo","Chart increasing","dados",["crescimento","alta","resultado","métrica","subiu"]),
 ("grafico-descendo","Chart decreasing","dados",["queda","baixa","perda","caiu"]),
 ("grafico-barras","Bar chart","dados",["dados","relatório","dashboard","métricas"]),
 ("saco-dinheiro","Money bag","dinheiro",["dinheiro","lucro","receita","faturamento"]),
 ("dinheiro","Dollar banknote","dinheiro",["dinheiro","pagamento","custo","preço"]),
 ("dinheiro-voando","Money with wings","dinheiro",["gasto","desperdício","prejuízo","dinheiro indo embora"]),
 ("moeda","Coin","dinheiro",["moeda","economia","troco","investimento"]),
 ("cartao-credito","Credit card","dinheiro",["pagamento","cartão","compra","assinatura"]),
 ("recibo","Receipt","dinheiro",["nota","recibo","conta","cobrança"]),
 ("abaco","Abacus","dados",["conta","cálculo","matemática"]),
 # trabalho
 ("maleta","Briefcase","trabalho",["trabalho","negócio","carreira","empresa"]),
 ("calendario","Spiral calendar","trabalho",["agenda","data","prazo","planejamento"]),
 ("prancheta","Clipboard","trabalho",["checklist","plano","lista","briefing"]),
 ("anotacao","Memo","trabalho",["nota","escrever","documento","requisito"]),
 ("alfinete","Pushpin","trabalho",["fixar","importante","lembrete"]),
 ("pasta","File folder","trabalho",["arquivo","organização","documentos"]),
 ("caixa","Package","trabalho",["entrega","produto","pacote","envio"]),
 ("aperto-maos","Handshake","trabalho",["acordo","parceria","negócio fechado","stakeholder"]),
 ("predio","Office building","trabalho",["empresa","corporativo","escritório"]),
 ("trofeu","Trophy","conquista",["conquista","vitória","prêmio","campeão"]),
 ("medalha","1st place medal","conquista",["primeiro lugar","medalha","melhor"]),
 ("diamante","Gem stone","conquista",["valor","premium","precioso","raro"]),
 ("livros","Books","trabalho",["estudo","conhecimento","aprender","leitura"]),
 ("formatura","Graduation cap","trabalho",["formação","curso","mentoria","aprender"]),
 # tempo
 ("despertador","Alarm clock","tempo",["prazo","urgência","acordar","hora"]),
 ("ampulheta","Hourglass not done","tempo",["tempo","espera","prazo acabando"]),
 ("cronometro","Stopwatch","tempo",["velocidade","rápido","cronômetro","tempo"]),
 # comunicação e tecnologia
 ("balao-fala","Speech balloon","comunicacao",["comentário","conversa","feedback","diálogo"]),
 ("balao-pensamento","Thought balloon","comunicacao",["pensamento","dúvida","reflexão"]),
 ("megafone","Megaphone","comunicacao",["anúncio","divulgar","marketing","aviso"]),
 ("sino","Bell","comunicacao",["notificação","alerta","lembrete","sino"]),
 ("envelope","Envelope","comunicacao",["e-mail","mensagem","carta","contato"]),
 ("celular","Mobile phone","tecnologia",["celular","app","WhatsApp","mobile"]),
 ("notebook","Laptop","tecnologia",["computador","trabalho remoto","sistema","software"]),
 ("robo","Robot","tecnologia",["IA","inteligência artificial","automação","bot"]),
 ("link","Link","tecnologia",["link","conexão","integração","link na bio"]),
 ("cadeado","Locked","tecnologia",["segurança","privacidade","bloqueado"]),
 ("escudo","Shield","tecnologia",["proteção","segurança","garantia"]),
 ("inseto","Bug","tecnologia",["bug","erro","problema","falha"]),
 ("bateria-fraca","Low battery","tecnologia",["cansaço","sem energia","esgotado"]),
 ("claquete","Clapper board","comunicacao",["vídeo","gravação","bastidores","ação"]),
 ("microfone","Studio microphone","comunicacao",["podcast","fala","entrevista","áudio"]),
 ("camera","Camera with flash","comunicacao",["foto","registro","momento"]),
 # reações e sinais
 ("pensativo","Thinking face","reacoes",["dúvida","pensando","será?","hmm"]),
 ("cabeca-explodindo","Exploding head","reacoes",["chocante","mind blown","surpresa"]),
 ("susto","Face screaming in fear","reacoes",["medo","susto","pânico","erro grave"]),
 ("estrelas-olhos","Star-struck","reacoes",["encantado","uau","incrível"]),
 ("oculos-escuros","Smiling face with sunglasses","reacoes",["confiante","tranquilo","de boa"]),
 ("monoculo","Face with monocle","reacoes",["analisando","curioso","investigando"]),
 ("festa","Partying face","reacoes",["festa","comemorar","aniversário"]),
 ("mao-na-boca","Face with hand over mouth","reacoes",["ops","segredo","surpresa"]),
 ("olhos","Eyes","reacoes",["olha isso","atenção","de olho"]),
 ("coracao","Red heart","sinais",["amor","carinho","gostei","coração"]),
 ("fogo","Fire","sinais",["em alta","quente","incrível","fogo"]),
 ("brilho","Sparkles","sinais",["novo","mágica","especial","brilho"]),
 ("estrela","Star","sinais",["destaque","favorito","avaliação","estrela"]),
 ("cem","Hundred points","sinais",["perfeito","100%","nota máxima"]),
 ("check","Check mark button","sinais",["certo","feito","aprovado","ok"]),
 ("xis","Cross mark","sinais",["errado","não","erro","proibido"]),
 ("alerta","Warning","sinais",["atenção","cuidado","risco","alerta"]),
 ("proibido","No entry","sinais",["proibido","pare","bloqueio"]),
 ("interrogacao","Red question mark","sinais",["pergunta","dúvida","por quê?"]),
 ("exclamacao","Red exclamation mark","sinais",["importante","atenção","exclamação"]),
 ("joinha","Thumbs up","gestos",["ok","aprovado","curti","joinha"]),
 ("palmas","Clapping hands","gestos",["parabéns","aplausos","bravo"]),
 ("maos-pra-cima","Raising hands","gestos",["comemoração","viva","finalmente"]),
 ("musculo","Flexed biceps","gestos",["força","consegui","disciplina"]),
 ("aceno","Waving hand","gestos",["oi","tchau","olá"]),
 ("maos-unidas","Folded hands","gestos",["gratidão","por favor","obrigado","fé"]),
 ("apontando-cima","Index pointing up","gestos",["dica","atenção","um ponto"]),
 ("apontando-direita","Backhand index pointing right","gestos",["próximo","veja","ao lado"]),
 ("apontando-baixo","Backhand index pointing down","gestos",["link na bio","abaixo","comente"]),
 ("confete","Party popper","conquista",["comemorar","lançamento","parabéns"]),
 ("presente","Wrapped gift","conquista",["presente","bônus","brinde","surpresa"]),
 ("balao","Balloon","conquista",["festa","aniversário","comemoração"]),
 # vida e casa
 ("casa","House","vida",["casa","lar","família"]),
 ("sol","Sun","vida",["dia","sol","verão","bom dia"]),
 ("lua","Crescent moon","vida",["noite","lua","descanso"]),
 ("arco-iris","Rainbow","vida",["esperança","depois da chuva","cores"]),
 ("cafe","Hot beverage","vida",["café","manhã","pausa","rotina"]),
 ("bolo","Birthday cake","vida",["aniversário","bolo","festa"]),
 ("aviao","Airplane","vida",["viagem","voo","férias"]),
 ("praia","Beach with umbrella","vida",["praia","férias","verão"]),
 ("carro","Automobile","vida",["carro","viagem","estrada"]),
 ("bicicleta","Bicycle","vida",["bicicleta","passeio","exercício"]),
 ("cachorro","Dog face","vida",["cachorro","pet","amigo"]),
 ("broto","Seedling","vida",["crescer","começo","semente","cuidado"]),
 ("girassol","Sunflower","vida",["alegria","sol","flor"]),
 ("rosa","Rose","vida",["rosa","flor","carinho","oferenda"]),
 ("flor-cerejeira","Cherry blossom","vida",["flor","primavera","delicado"]),
 ("buque","Bouquet","vida",["flores","homenagem","presente"]),
 ("notas-musicais","Musical notes","vida",["música","som","trilha"]),
 ("violao","Guitar","vida",["violão","música","roda"]),
 ("bola","Soccer ball","vida",["futebol","jogo","esporte"]),
 # comunidade e terreiro (neutros, sem símbolo sagrado)
 ("ticket","Admission tickets","comunidade",["senha","ingresso","fila","entrada"]),
 ("vela","Candle","comunidade",["vela","luz","fé","oração"]),
 ("erva","Herb","comunidade",["erva","natureza","folha","banho"]),
 ("onda","Water wave","comunidade",["mar","água","onda"]),
 ("pessoas","People hugging","comunidade",["comunidade","acolhimento","abraço","juntos"]),
 ("grupo","Busts in silhouette","comunidade",["equipe","grupo","pessoas","membros"]),
 # gestão de produto e reações (acrescentados em 2026-10 para o @pontes_brain, servem a todas as marcas)
 ("semaforo","Vertical traffic light","gestao",["status","farol","verde amarelo vermelho","RAG","report"]),
 ("cadeado-aberto","Unlocked","estrategia",["destravar","desbloquear","liberado","acesso"]),
 ("porta","Door","gestao",["gate","passagem","próxima fase","entrada"]),
 ("caracol","Snail","tempo",["atraso","lento","devagar","prazo"]),
 ("tartaruga","Turtle","tempo",["lento","constante","devagar e sempre"]),
 ("tesoura","Scissors","gestao",["cortar escopo","corte","priorizar","MVP"]),
 ("extintor","Fire extinguisher","gestao",["apagar incêndio","crise","urgência","emergência"]),
 ("boia","Ring buoy","gestao",["resgate","salvar projeto","socorro","ajuda"]),
 ("balanca","Balance scale","estrategia",["trade-off","priorização","equilíbrio","decisão"]),
 ("ciclo","Counterclockwise arrows button","processo",["ciclo","PDCA","iteração","repetir","melhoria contínua"]),
 ("dado","Game die","estrategia",["risco","aposta","sorte","incerteza"]),
 ("bomba","Bomb","sinais",["crise","risco","explodir","problema"]),
 ("derretendo","Melting face","reacoes",["burnout","cansaço","sobrecarga","calor"]),
 ("tonto","Face with spiral eyes","reacoes",["confuso","perdido","caos","tontura"]),
 ("dormindo","Sleeping face","reacoes",["parado","travado","tédio","sono"]),
 ("voce","Index pointing at the viewer","gestos",["você","apontando para você","chamada","CTA"]),
 ("negativo","Thumbs down","gestos",["não","ruim","reprovado","erro"]),
 ("coroa","Crown","conquista",["liderança","dono","rei","melhor"]),
 ("telescopio","Telescope","estrategia",["visão","longo prazo","futuro","roadmap"]),
 ("microscopio","Microscope","analise",["detalhe","análise","diagnóstico","investigar"]),
 ("ima","Magnet","crescimento",["atrair","clientes","leads","atração"]),
 ("ancora","Anchor","estrategia",["âncora","estabilidade","preso","base"]),
 ("tijolo","Brick","processo",["base","fundação","construir","passo a passo"]),
 ("construcao","Building construction","processo",["em construção","obra","delivery","construir"]),
 ("porca-parafuso","Nut and bolt","processo",["detalhe técnico","engrenagem","execução","operação"]),
 ("caixa-entrada","Inbox tray","trabalho",["intake","demanda","entrada","backlog"]),
 ("fichario","Card index dividers","trabalho",["organizar","documentação","fichas","categorias"]),
 ("regua","Straight ruler","dados",["medir","métrica","KPI","régua"]),
 ("lapis","Pencil","trabalho",["escrever","rascunho","planejar","editar"]),
 ("correntes","Chains","gestao",["dependências","preso","amarras","integração"]),
 ("fantasma","Ghost","reacoes",["sumiu","ghosting","sem resposta","invisível"]),
 ("pare","Stop sign","sinais",["pare","stop","parar","limite"]),
 ("continencia","Saluting face","reacoes",["entendido","sim senhor","respeito","missão"]),
 ("nerd","Nerd face","reacoes",["nerd","técnico","estudioso","dica"]),
 ("segredo","Shushing face","reacoes",["segredo","silêncio","não conta","bastidores"]),
 ("montanha","Mountain","crescimento",["meta","desafio","subir","topo"]),
 ("escrevendo","Writing hand","trabalho",["escrever","anotar","assinar","documentar"]),
 ("olho","Eye","analise",["visibilidade","observar","transparência","ver"]),
 ("computador","Desktop computer","tecnologia",["computador","sistema","software","trabalho"]),
 ("lixeira","Wastebasket","gestao",["descartar","jogar fora","desperdício","cortar"]),
 ("marcadores","Bookmark tabs","trabalho",["referência","estudo","documentos","marcadores"]),
 ("coracao-fogo","Heart on fire","sinais",["paixão","amor pelo produto","intenso"]),
 ("estrela-brilhante","Glowing star","conquista",["destaque","brilhar","excelência","estrela"]),
 ("ampulheta-fim","Hourglass done","tempo",["acabou o tempo","prazo vencido","deadline"]),
 ("caderno","Spiral notepad","trabalho",["caderno","notas","ata","anotações"]),
 ("martelo","Hammer","processo",["decisão","martelo batido","construir","aprovado"]),
 ("zumbi","Man zombie","gestao",["projeto zumbi","morto-vivo","parado","sem dono"]),
 ("sos","Sos button","sinais",["socorro","SOS","emergência","ajuda"]),
]

# id, slug no Simple Icons, tags (pt). "claude" e "chatgpt" já estão em logos/ (versões anteriores do editor).
LOGOS = [
    ("gemini", "googlegemini", ["IA", "Google", "Gemini"]), ("perplexity", "perplexity", ["IA", "busca"]),
    ("deepseek", "deepseek", ["IA"]), ("mistral", "mistralai", ["IA"]), ("copilot", "githubcopilot", ["IA", "código"]),
    ("cursor", "cursor", ["IA", "código", "editor"]), ("notion", "notion", ["documentação", "wiki", "produtividade"]),
    ("figma", "figma", ["design", "protótipo", "UX"]), ("jira", "jira", ["backlog", "sprint", "ágil"]),
    ("trello", "trello", ["kanban", "tarefas"]), ("miro", "miro", ["quadro", "workshop", "discovery"]),
    ("asana", "asana", ["tarefas", "projetos"]), ("clickup", "clickup", ["tarefas", "projetos"]),
    ("airtable", "airtable", ["base de dados", "planilha"]), ("github", "github", ["código", "repositório"]),
    ("vercel", "vercel", ["deploy", "site"]), ("supabase", "supabase", ["banco de dados", "backend"]),
    ("n8n", "n8n", ["automação", "no-code"]), ("zapier", "zapier", ["automação", "no-code"]),
    ("make", "make", ["automação", "no-code"]), ("obsidian", "obsidian", ["notas", "segundo cérebro"]),
    ("loom", "loom", ["vídeo", "assíncrono"]), ("hubspot", "hubspot", ["CRM", "vendas"]),
    ("stripe", "stripe", ["pagamento", "SaaS"]), ("shopify", "shopify", ["e-commerce", "loja"]),
    ("google", "google", ["Google", "busca"]), ("gmail", "gmail", ["e-mail"]), ("google-drive", "googledrive", ["arquivos"]),
    ("google-sheets", "googlesheets", ["planilha", "dados"]), ("google-calendar", "googlecalendar", ["agenda"]),
    ("google-meet", "googlemeet", ["reunião", "chamada"]), ("zoom", "zoom", ["reunião", "chamada"]),
    ("discord", "discord", ["comunidade", "chat"]), ("telegram", "telegram", ["mensagem"]),
    ("whatsapp", "whatsapp", ["mensagem", "WhatsApp", "atendimento"]), ("instagram", "instagram", ["rede social", "Reels"]),
    ("youtube", "youtube", ["vídeo", "canal"]), ("tiktok", "tiktok", ["vídeo curto"]), ("x", "x", ["rede social", "Twitter"]),
    ("meta", "meta", ["Facebook", "anúncios"]), ("spotify", "spotify", ["música", "podcast"]), ("apple", "apple", ["iPhone", "Mac"]),
    ("python", "python", ["código", "dados"]), ("pix", "pix", ["pagamento", "Brasil"]), ("nubank", "nubank", ["banco", "fintech"]),
    ("mercado-pago", "mercadopago", ["pagamento"]),
]
LOGOS_ANTIGOS = [("claude", "Claude", ["IA", "Anthropic", "Claude"]), ("chatgpt", "ChatGPT", ["IA", "OpenAI", "ChatGPT"])]


def baixar(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "edicao-video/2"}), timeout=60).read()


def png_fluent(pasta):
    slugs = {pasta.lower().replace(" ", "_"), pasta.lower().replace(" ", "_").replace("-", "_")}
    for sub in [f"{d}{s}_3d{x}.png" for s in slugs for d, x in (("3D/", ""), ("Default/3D/", "_default"))]:
        try:
            return baixar(FLUENT + urllib.parse.quote(f"{pasta}/{sub}"))
        except Exception:
            continue
    raise SystemExit(f"Fluent Emoji sem 3D: {pasta}")


def cor_legivel(hexcor):
    r, g, b = (int(hexcor[i:i + 2], 16) for i in (0, 2, 4))
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return "FFFFFF" if lum < 0.22 else hexcor  # logo preto some no fundo escuro: vira branco


def main():
    import cairosvg
    (DEST / "renders").mkdir(parents=True, exist_ok=True)
    (DEST / "logos").mkdir(parents=True, exist_ok=True)
    itens = []
    for iid, pasta, cat, tags in RENDERS:
        p = DEST / "renders" / f"{iid}.png"
        if not p.exists():
            p.write_bytes(png_fluent(pasta))
        itens.append({"id": iid, "nome": pasta, "tipo": "render", "categoria": cat, "tags": tags, "arquivo": f"renders/{iid}.png",
                      "fonte": "Microsoft Fluent Emoji 3D", "licenca": "MIT", "fluent": pasta})
    dados = json.loads(baixar(SIMPLE_ICONS + "data/simple-icons.json"))
    dados = {x.get("slug") or x["title"].lower(): x for x in (dados if isinstance(dados, list) else dados["icons"])}
    for iid, nome, tags in LOGOS_ANTIGOS:
        itens.append({"id": iid, "nome": nome, "tipo": "extrusao", "categoria": "logos", "tags": tags, "arquivo": f"logos/{iid}.png",
                      "fonte": "Simple Icons", "licenca": "CC0 1.0", "aviso": "marca registrada do dono; uso editorial"})
    for iid, slug, tags in LOGOS:
        p = DEST / "logos" / f"{iid}.png"
        cor = cor_legivel(dados[slug]["hex"])
        if not p.exists():
            svg = baixar(SIMPLE_ICONS + f"icons/{slug}.svg").decode().replace("<svg ", f'<svg fill="#{cor}" ', 1)
            p.write_bytes(cairosvg.svg2png(bytestring=svg.encode(), output_width=512, output_height=512))
        itens.append({"id": iid, "nome": dados[slug]["title"], "tipo": "extrusao", "categoria": "logos", "tags": tags,
                      "arquivo": f"logos/{iid}.png", "cor": f"#{cor}", "fonte": "Simple Icons", "licenca": "CC0 1.0",
                      "aviso": "marca registrada do dono; uso editorial"})
    cat = {"versao": 1, "observacao": "Gerado por ferramentas/montar_3d.py. Objetos de identidade de uma marca ficam em marcas/<id>/3d/.",
           "itens": itens}
    (DEST / "catalogo.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(itens)} objetos")


if __name__ == "__main__":
    main()
