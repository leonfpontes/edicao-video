# Changelog

## Não lançado

### Novo

- **Tour pela casa no automático** (`motor/tour.py`): no vídeo em que a câmera anda pelo ambiente, o `analisar` escreve
  até 3 capítulos por cômodo (fala de passagem, mudança de cor do ambiente, caminhada cortada; título do lugar citado)
  com transição `luz` e sopro, e até 8 rótulos editoriais presos ao ponto para onde o dedo aponta (`cena.json` ganha
  "apontar" e a assinatura de cor de cada segundo). No vídeo do GiraHub saiu a mesma estrutura da v4 feita à mão.
- **Pausas pelo áudio** (`motor/pausas.py`): o `analisar` acerta o começo e o fim das palavras que o Whisper esticou
  sobre o silêncio; o rascunho do vídeo do GiraHub caiu de 84 s para 66 s. `--sem-aparar` usa os tempos crus.
- `legendas.correcoes` padrão do GiraHub para as entidades (echu → Exu, ochum → Oxum, xalá → Oxalá, fá → Ifá).

### Corrigido

- Render em vários processos com `fixar`: o cache de trilhas (`_cache/fixar.json`) agora é gravado de forma atômica
  (antes, dois processos podiam ler o arquivo pela metade).

- **Direção de arte no motor** (lições da edição do GiraHub):
  - o `analisar` abre pela frase mais forte, tira o anúncio do começo e não repete o trecho (`montar_gancho`);
  - `intro.apos_gancho`: a vinheta entra logo depois do gancho;
  - tour detectado pela cena (câmera andando em mais de 25% do vídeo) liga `cor.igualar_luz` e põe o roteiro de
    documentário no relatório;
  - `anotacao` com `estilo: "editorial"` (sobrelinha em sans e nome em serifa itálica, ponto e fio) e `sem_legenda`
    em qualquer elemento;
  - legenda com `"marcacao": "enfase"` (padrão no GiraHub);
  - regras de direção de arte em `docs/diretor-e-entrega.md` e nas três skills.
- **Objetos 3D criados sob demanda** (`motor/criar3d.py`, `biblioteca criar 3d`, ou `fluent`/`emoji` no `objeto3d`):
  Fluent Emoji 3D, emoji extrudado ou placa da marca. Primeiros criados: `casa`, `broto`, `balao-fala`.
- **Rótulo preso a um objeto do ambiente**: `"fixar": [t, x, y]` rastreia o ponto pelo fluxo óptico, também com `na`/`ate`;
  `anotacao` ganha `caixa` e põe a mira no objeto.
- **Leitura da cena** no `analisar` (`motor/cena.py`, `cena.json`, `--sem-cena` desliga): gestos da mão (dedo para cima,
  apontar para a câmera, mão aberta, joinha), aceno de cabeça (sim e não) e câmera (giro pelo ambiente, câmera se
  afastando). Cada leitura vira brilho, ondas, círculo, check, xis, luz, `whip` ou zoom `abre`, que acompanham o
  movimento.
- **Elementos que acompanham o movimento**: campo `"seguir"` (trilha na fonte, projetada depois do enquadramento) e
  `dx`/`dy`.
- Zoom `"modo": "abre"` (entra fechado e abre).
- `"diretor": {"calmo": true}` no `marca.json` (GiraHub): a cena não usa tranco de zoom nem marca a mão sem o rosto.
- Intro e CTA ficam sempre ligados, também no GiraHub em fala de fé; só saem com pedido do Leonardo.
- **Peças fixas no Pencil**: capa de Reel do @pontes_brain em `marcas/pontes_brain/pencil/capa-reel.pen` (fonte) e
  `capa-reel.png` (1080×1920); convenção documentada em `docs/marcas.md`.
- **Diretor automático** no `analisar` (`motor/diretor.py`, `--sem-diretor` desliga):
  - corta vícios e tomadas repetidas;
  - escolhe as ênfases da legenda;
  - alterna o zoom nos jump cuts (`"salto"`) e dá punch nas ênfases;
  - dá nota ao gancho e aponta a frase mais forte;
  - sugere elementos e termos de b-roll.

  Relatório em `diretor.json` e no fim da `transcricao.txt`.
- **Render mais rápido**:
  - trechos em paralelo, cada um aquecendo câmera e recorte para sair igual ao render corrido (`--processos`);
  - cache do recorte da pessoa em `_cache/`;
  - looks e cor por LUT;
  - tela em perspectiva otimizada.

  No estilo vitrine, o re-render ficou 4x mais rápido.
- **Prévia rápida**: `renderizar --previa --de S --ate S` gera `previa.mp4` a 10 quadros/s, só da janela pedida, com áudio.
- **Conferência visual** (`motor/qa.py`) em todo render, com `conferencia.json`. Ela aponta:
  - elemento ou legenda fora da área segura;
  - elemento cobrindo o rosto, legenda sobre o rosto ou brigando com um elemento;
  - legenda sem contraste;
  - loudness, duração e gancho fraco.
- **`linha-do-tempo`**: página HTML com o vídeo e as trilhas do EDL.
- **`exportar`**: `legenda.srt`, capa limpa, rascunho do post (termina no CTA da marca), `reel.mp4` até 20 MB, outros formatos
  (`--formatos`) e a entrada da agenda do insta_report (`--quando`, `--insta-report`).
- **`renderizar --formato`**: o mesmo EDL em `feed` ou `horizontal`.
- **`broll`**: b-roll vertical do Pexels com `PEXELS_API_KEY`, baixado para a pasta do vídeo com a licença ao lado.
- **Cor**:
  - LUT 3D `.cube` (`cor.lut`, `lut_intensidade`);
  - pele protegida nos looks de cor;
  - cor igual entre clipes gravados em momentos diferentes.
- **Legendas**:
  - quebra por sentido (o bloco não termina em "de", "o", "que");
  - `emoji`: objeto 3D da biblioteca pula acima da legenda na palavra certa.

- **Estilos de edição** (`"estilo"` no EDL, `analisar --estilo`, `editor.py estilos`): `tutorial_passos`,
  `tela_perspectiva` e `vitrine`, presets que ajustam legenda, sons, corte de pausas e o aviso de ritmo.
- **Planos por segmento** (`"plano"`): `rosto`, `dividido` (palco de motion em cima, rosto embaixo) e `motion`; a
  legenda acompanha a linha do plano. `motor/planos.py`.
- **Looks por segmento** (`"look"`): `pb`, `pb_acento`, `duotom`, `quente`, `frio`, `limpo`, `noite` e `adesivo`
  (pessoa recortada com contorno sobre fundo chapado).
- **Legenda `limpa`**: 1 ou 2 palavras, branco, sem caixa nem contorno, sombra macia.
- **Motion de estilo** (`motor/motion.py`): `passo`, `digitacao`, `janela`, `arvore`, `mapa`, `comentario`, `icone`,
  `carrossel`, `titulo_caixa`, `titulo_editorial`, `bilhete`, `anotacao`, `neon`, `texto_atras` (atrás da pessoa, com
  recorte automático) e `hud_rosto` (segue o rosto). `som` com `rotulo` mostra o som na tela.
- **Tela em perspectiva** (`broll` com `perspectiva`): plano 3D com câmera por pontos-chave, profundidade de campo e
  luz quente. **Bolha de rosto** (`broll` com `bolha`).
- **Aviso de ritmo**: com `parado_max`, o render mede o maior trecho sem mudança visual.
- **Fontes de estilo** (OFL): DM Serif Display, Anton, Space Mono e Caveat, com licenças em `biblioteca/fontes/LICENCAS.md`.
- **Estilos de referência** em `docs/estilos-de-referencia.md`: três estilos de Reels estudados (tela em perspectiva,
  tutorial em passos, vitrine de estilos), com números medidos, receita para o motor atual e lista do que falta construir.

### Mudou

- **Nunca borda esticada**: a estabilização (`--estabilizar`) passou do `deshake` com borda esticada para o vid.stab
  em duas passadas com zoom adaptativo (aproxima só o necessário, nunca estica a borda); o enquadramento não sai mais
  da fonte (a respiração do zoom ficava abaixo de 1 e o tremor do punch passava da borda); o efeito `tremor` e os fundos
  aproximam em vez de espelhar. O `analisar` confere o vídeo estabilizado e o render reprova "borda esticada".
- Correções da legenda valem com pontuação colada ("echu," vira "Exu,").
- Ajustes do primeiro teste com vídeos reais:
  - "um" e "uma" não contam mais como número no diretor ("um vídeo" não é número concreto);
  - o gancho da conferência é medido na abertura do vídeo editado, não na do bruto;
  - a legenda quebra em duas linhas antes de chegar aos botões do Reels (`legendas.largura_max`, padrão 0,70);
  - o rascunho do `post.txt` usa as `correcoes` da legenda, abre com maiúscula e não leva CTA quando o vídeo não tem;
  - marcas com enquadramento contínuo (`"diretor": {"alternar_zoom": false}`, ligado no @pontes_brain e no GiraHub) não
    recebem o zoom alternado nos jump cuts;
  - `analisar --modelo` aceita a pasta de um modelo Whisper local.
- Caminhos de arquivo no EDL são relativos à pasta do próprio `edl.json`, não à pasta de onde o comando roda.
- O b-roll é lido pelo instante, na velocidade real do arquivo (gravação de tela a 60 fps não fica mais em câmera lenta).
- Por causa da quebra por sentido, as folhas de referência de todas as marcas foram regeradas: a legenda de teste agora
  fecha o bloco em "palavra", não em "por".

## 2.1.0 (2026-10-29)

Assets em alta para Reels (pesquisa de tendências de outubro de 2026), pensados para o @pontes_brain e servindo a todas as marcas.

### Novo

- **Biblioteca de sons** (`biblioteca/sons/`): 38 efeitos sonoros (whooshes, risers, impactos, interface, papel, lápis,
  teclado, notificação, moedas), gravações CC0 do OpenGameArt e efeitos próprios desenhados em `ferramentas/montar_sons.py`,
  nivelados e com o instante do pico (`ataque`) para alinhar ao corte ou à palavra. `editor.py biblioteca listar sons`.
- **Sons no EDL**: `"som"` em segmentos e elementos (id ou `false`) e o elemento `{"tipo": "som"}`. Marcas com
  `"sons": {"modo": "biblioteca"}` tocam um som por tipo de transição, de elemento e de efeito, alternando variações.
- **4 transições**: `giro` (giro 3D), `rasgo` (papel rasgado), `vidro` (vidro líquido) e `luz` (queima de luz).
- **8 efeitos**: `cartao_vidro`, `notificacao`, `carregando`, `checklist`, `tipografia` (cinética), `marca_texto`,
  `reacoes`, `reflexo` e o painel de vidro líquido reutilizável (`painel_vidro`).
- **48 objetos 3D** (Fluent Emoji, MIT) para gestão de produto: semáforo, zumbi, caracol, tesoura, extintor, boia,
  balança, porta, ciclo, correntes, régua, telescópio, microscópio, cadeado aberto, coroa, "você"…
- **3D do @pontes_brain**: placas `g1` a `g4` dos gates e o ciclo `pdca` (`ferramentas/gerar_3d_pontes_brain.py`).

### Mudou

- O @pontes_brain passa a usar a biblioteca de sons (vinheta, transições, elementos e CTA). GiraHub e @leopontesrp não mudam.
- Efeitos ganham `som` no catálogo; `biblioteca verificar` confere os sons.


## 2.0.0 (2026-10-29)

Repositório profissionalizado, com bibliotecas compartilhadas e isolamento entre marcas.

### Novo

- **Isolamento entre marcas**: `--marca` obrigatório (sem padrão), pasta por marca com sandbox de arquivos, vinhetas,
  fundos e Leo com dono, termos exclusivos por marca, guarda do EDL (`motor/guarda.py`), auditoria dos arquivos abertos,
  selo da marca nos metadados do vídeo e `editor.py conferir`.
- **Biblioteca 3D**: 167 objetos (119 renders do Fluent Emoji 3D, 48 logos extrudados do Simple Icons), com busca.
- **Biblioteca de músicas**: 35 faixas reais CC BY 4.0, com clima, energia, BPM, gênero, instrumentos e crédito;
  download conferido por sha256 e `creditos.txt` no render.
- **Biblioteca de efeitos**: 20 layers procedurais na paleta da marca (luz, textura, impacto, celebração, anotação,
  informação), ancorados na fala.
- `editor.py marcas`, `editor.py biblioteca listar|baixar|verificar|previa|catalogo`.
- `manifesto.json` em todo render.
- Testes de unidade (pytest), CI no GitHub Actions, Makefile, `pyproject.toml`.
- README vitrine, CLAUDE.md, AGENTS.md, CONTRIBUTING.md e docs/.

### Mudou

- `editor.py` virou o pacote `motor/` (mesmo visual, regressão com diferença 0,00 em todas as marcas).
- `marcas/<id>.json` → `marcas/<id>/marca.json`, com os arquivos da marca ao lado.
- `assets/` dividido entre `marcas/<id>/` (identidade) e `biblioteca/` (compartilhado).
- Skills em `skills/<skill>/SKILL.md`.
- Música no EDL por `"faixa"` (id do catálogo); `"arquivo"` antigo continua funcionando.
- `musica_obrigatoria` → `"musica": {"politica": "proibida" | "opcional" | "obrigatoria"}`. O @pontes_brain passa a
  recusar música no vídeo (o Leonardo põe a música no Instagram).

### Removido

- `PROMPT-MESTRE.md` e `PROMPT-instagram-pessoal.md` (duplicavam as skills).
- `assets/musicas/` (as faixas agora vêm da biblioteca).

## 1.x

Editor de arquivo único para @pontes_brain, depois GiraHub e @leopontesrp.
