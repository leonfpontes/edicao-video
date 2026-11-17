"""`linha-do-tempo`: página HTML com o vídeo e a linha do tempo do EDL (cortes, planos, looks, elementos, zooms,
legendas, sons e os avisos da conferência). Clicar num bloco leva o vídeo àquele instante; o cursor acompanha o play.

Serve para revisar uma edição sem ler o JSON: o agente gera, a pessoa abre no navegador ao lado do final.mp4.
"""
import html
import json
from pathlib import Path

from .config import FPS
from .renderizar import Contexto

CORES_TRILHA = {"segmento": "#3b6ea8", "gancho": "#b5651d", "elemento": "#7a5ea8", "zoom": "#2f8f6a", "legenda": "#8a8f98",
                "som": "#a8843b", "aviso": "#c0392b", "vinheta": "#555b66"}


def dados(ctx):
    """Blocos da linha do tempo, em segundos do vídeo final (com a vinheta)."""
    di = ctx.dur_intro
    blocos = []
    if di:
        blocos.append({"trilha": "Cortes", "de": 0, "ate": di, "rotulo": "vinheta", "tipo": "vinheta", "info": "abertura da marca"})
    for s in ctx.segs:
        d = s["n"] / FPS
        info = [f"original {s['qa']:.2f}–{s['qb']:.2f}s", f"zoom {s.get('zoom', 1.0)}"]
        for k in ("plano", "look", "transicao"):
            if s.get(k):
                info.append(f"{k}: {s[k]}")
        if s.get("salto"):
            info.append("salto de zoom no corte")
        blocos.append({"trilha": "Cortes", "de": di + s["o"], "ate": di + s["o"] + d, "tipo": "gancho" if s.get("gancho") else "segmento",
                       "rotulo": (s.get("texto") or f"corte {s.get('id', '')}")[:60], "info": " · ".join(info), "texto": s.get("texto", "")})
        if s.get("plano", "rosto") != "rosto" or s.get("look"):
            blocos.append({"trilha": "Planos e looks", "de": di + s["o"], "ate": di + s["o"] + d, "tipo": "segmento",
                           "rotulo": " · ".join(x for x in (s.get("plano"), s.get("look")) if x), "info": ""})
    for e in ctx.els.items:
        if e["tipo"] == "som":
            blocos.append({"trilha": "Sons", "de": di + e["o_ini"], "ate": di + max(e["o_fim"], e["o_ini"] + 0.3), "tipo": "som",
                           "rotulo": e.get("rotulo") or e.get("nome", "som"), "info": f"som {e.get('nome')}"})
            continue
        rot = e.get("texto") or e.get("nome") or e.get("titulo") or e.get("centro") or e["tipo"]
        trilha = "B-roll" if e["tipo"] == "broll" else "Elementos"
        blocos.append({"trilha": trilha, "de": di + e["o_ini"], "ate": di + e["o_fim"], "tipo": "elemento",
                       "rotulo": f"{e['tipo']}: {rot}"[:50],
                       "info": ", ".join(f"{k}={v}" for k, v in e.items() if k in ("na", "ate", "x", "y", "cor", "nome", "numero"))})
    for z in ctx.zooms:
        a, b = ctx.map_out(z["ini"]), ctx.map_out(z["fim"])
        if b > a:
            blocos.append({"trilha": "Zooms", "de": di + a, "ate": di + b + 0.35, "tipo": "zoom",
                           "rotulo": f"{z.get('modo', 'suave')} ×{z.get('fator', 1.2)}", "info": ""})
    if ctx.leg:
        for w in ctx.an["palavras"]:
            if any(qa <= (w["ini"] + w["fim"]) / 2 < qb for qa, qb in ctx.keep):
                a = ctx.map_out(w["ini"])
                blocos.append({"trilha": "Legenda", "de": di + a, "ate": di + a + (w["fim"] - w["ini"]), "tipo": "legenda",
                               "rotulo": w["t"], "info": f"confiança {w.get('p', 1):.2f}"})
    if ctx.dur_cta:
        blocos.append({"trilha": "Cortes", "de": di + ctx.dur_fala, "ate": ctx.total, "tipo": "vinheta", "rotulo": "CTA", "info": ""})
    conf = ctx.pasta / "conferencia.json"
    if conf.exists():
        for p in json.load(open(conf)).get("problemas", []):
            blocos.append({"trilha": "Avisos", "de": p["de"], "ate": max(p["ate"], p["de"] + 0.3), "tipo": "aviso",
                           "rotulo": p["problema"], "info": p["onde"]})
    return blocos


def gerar(edl_p, video=None):
    ctx = Contexto(edl_p, falar=False, rapido=True)
    pasta = ctx.pasta
    if video is None:
        video = next((n for n in (ctx.edl.get("saida") or "final.mp4", "previa.mp4") if (pasta / n).exists()), "final.mp4")
    diretor = json.load(open(pasta / "diretor.json")) if (pasta / "diretor.json").exists() else {}
    g = diretor.get("gancho", {})
    resumo = f"Gancho {g['nota']}/10. " + "; ".join(g.get("motivos", [])) if g else ""
    info = {"total": ctx.total, "blocos": dados(ctx), "cores": CORES_TRILHA,
            "ordem": ["Cortes", "Planos e looks", "B-roll", "Elementos", "Zooms", "Legenda", "Sons", "Avisos"]}
    pagina = MODELO.replace("__TITULO__", html.escape(f"Linha do tempo · {pasta.name}"))
    pagina = pagina.replace("__VIDEO__", html.escape(video)).replace("__RESUMO__", html.escape(resumo))
    pagina = pagina.replace("__DADOS__", json.dumps(info, ensure_ascii=False).replace("</", "<\\/"))
    saida = pasta / "linha_do_tempo.html"
    saida.write_text(pagina)
    return saida


def cmd_linha_tempo(a):
    saida = gerar(Path(a.edl).resolve(), a.video)
    print(f"Linha do tempo: {saida} (abra no navegador, na mesma pasta do vídeo)")


MODELO = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITULO__</title>
<style>
:root{--fundo:#f6f4ef;--cartao:#fff;--texto:#1d2330;--suave:#6b7280;--linha:#e3e0d8;--cursor:#c0392b}
@media (prefers-color-scheme:dark){:root{--fundo:#12151c;--cartao:#1b2029;--texto:#e8e6e1;--suave:#9aa1ad;--linha:#2c323d}}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--texto);font:14px/1.45 system-ui,-apple-system,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px;display:grid;grid-template-columns:minmax(0,300px) minmax(0,1fr);gap:16px}
@media (max-width:760px){main{grid-template-columns:1fr}}
video{width:100%;border-radius:10px;background:#000;aspect-ratio:9/16;object-fit:contain}
h1{font-size:18px;margin:0 0 4px}.suave{color:var(--suave)}
.painel{background:var(--cartao);border:1px solid var(--linha);border-radius:10px;padding:12px;overflow:hidden}
.tempo{position:relative;overflow-x:auto}.regua,.trilha{position:relative;height:30px;min-width:100%}
.trilha{border-top:1px solid var(--linha);height:auto}.nome{position:sticky;left:0;z-index:2;font-size:12px;color:var(--suave);padding:6px 0;width:110px;
background:var(--cartao)}
.linha{display:flex}.faixa{position:relative;flex:1;height:30px}
.bloco{position:absolute;top:4px;height:22px;border-radius:5px;color:#fff;font-size:11px;padding:3px 6px;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;cursor:pointer;opacity:.92}.bloco:hover{opacity:1;outline:2px solid var(--texto)}
.cursor{position:absolute;top:0;bottom:0;width:2px;background:var(--cursor);pointer-events:none;z-index:3}
.marca{position:absolute;top:0;font-size:10px;color:var(--suave);border-left:1px solid var(--linha);padding-left:3px;height:30px}
#detalhe{min-height:44px;margin-top:10px}#zoom{width:140px}
</style></head><body><main>
<section><video id="v" src="__VIDEO__" controls playsinline></video></section>
<section class="painel"><h1>__TITULO__</h1><p class="suave">__RESUMO__</p>
<label class="suave">Zoom da linha <input id="zoom" type="range" min="1" max="8" step="0.5" value="1"></label>
<div class="tempo" id="tempo"></div><div id="detalhe" class="suave">Clique num bloco para ir ao instante e ver os detalhes.</div></section>
</main>
<script>
const D=__DADOS__;const v=document.getElementById('v');const tempo=document.getElementById('tempo');
const det=document.getElementById('detalhe');let escala=1;
function fmt(t){return t.toFixed(2)+'s'}
function desenhar(){tempo.innerHTML='';const larg=Math.max(tempo.clientWidth-110,300)*escala;
 const pct=t=>(t/D.total*larg)+'px';
 const regua=document.createElement('div');regua.className='linha';regua.innerHTML='<div class="nome"></div>';
 const fr=document.createElement('div');fr.className='faixa';fr.style.minWidth=larg+'px';
 const passo=D.total>60?10:(D.total>20?5:1);for(let t=0;t<=D.total;t+=passo){const m=document.createElement('div');m.className='marca';
 m.style.left=pct(t);m.textContent=t+'s';fr.appendChild(m)}regua.appendChild(fr);tempo.appendChild(regua);
 for(const nome of D.ordem){const bl=D.blocos.filter(b=>b.trilha===nome);if(!bl.length)continue;
  const l=document.createElement('div');l.className='linha trilha';const n=document.createElement('div');n.className='nome';n.textContent=nome;
  const f=document.createElement('div');f.className='faixa';f.style.minWidth=larg+'px';
  const fins=[];for(const b of bl.sort((x,y)=>x.de-y.de)){let k=fins.findIndex(t=>t<=b.de+0.01);if(k<0){k=fins.length;fins.push(0)}
   fins[k]=b.ate;b.faixa=k}
  f.style.height=l.style.height=(fins.length*26+4)+'px';
  for(const b of bl){const e=document.createElement('div');e.className='bloco';e.style.left=pct(b.de);e.style.top=(4+b.faixa*26)+'px';
   e.style.width=Math.max(b.ate-b.de,0.05)/D.total*larg+'px';e.style.background=D.cores[b.tipo]||'#666';e.textContent=b.rotulo;
   e.title=b.rotulo+' ('+fmt(b.de)+'–'+fmt(b.ate)+')';
   e.onclick=()=>{v.currentTime=b.de;det.textContent='';const s=document.createElement('strong');s.textContent=b.rotulo;det.append(s,
    document.createTextNode(' · '+fmt(b.de)+' a '+fmt(b.ate)+(b.info?' · '+b.info:'')+(b.texto?' · "'+b.texto+'"':'')))};f.appendChild(e)}
  l.append(n,f);tempo.appendChild(l)}
 const c=document.createElement('div');c.className='cursor';c.id='cursor';tempo.appendChild(c);mover()}
function mover(){const c=document.getElementById('cursor');if(!c)return;const larg=Math.max(tempo.clientWidth-110,300)*escala;
 c.style.left=(110+v.currentTime/D.total*larg)+'px'}
v.addEventListener('timeupdate',mover);document.getElementById('zoom').oninput=e=>{escala=+e.target.value;desenhar()};
addEventListener('resize',desenhar);desenhar();
</script></body></html>
"""
