# Testes e CI

```bash
make lint        # ruff
make testes      # pytest: rápidos, sem vídeo
make verificar   # catálogos, licenças e arquivos das bibliotecas
make regressao   # editor.py testar: visual + isolamento + render ponta a ponta
make tudo        # os quatro
```

## Testes de unidade (`tests/`)

| Arquivo | Cobre |
|---|---|
| `test_marcas.py` | Toda marca é válida; não existe marca padrão; `ativar` troca tudo; sandbox de arquivos; vinheta, fundo e Leo com dono; o `marca.json` de uma marca não cita outra |
| `test_guarda.py` | Cada recusa da guarda: EDL sem marca ou de outra marca, análise trocada, termos, CTA, Leo, arquivos, 3D próprio, cor solta, auditoria |
| `test_efeitos.py` | Os 20 efeitos desenham, são determinísticos, mudam com a paleta e recusam cor fora dela |
| `test_bibliotecas.py` | Ids únicos, licenças livres, arquivos 3D presentes, músicas com todas as tags, política de música, 3D próprio de marca, catálogo de efeitos em dia |

## Regressão (`editor.py testar`)

Para cada marca:

1. **Visual**: desenha a folha da marca (vinheta em 5 instantes, fundo, CTA, título, destaque, legenda, marca d'água) e
   compara com `testes/referencia/<marca>.png`. Diferença acima do limite falha e grava a folha atual em `testes/_tmp/`.
2. **Isolamento**: tenta passar um EDL com o termo exclusivo de cada outra marca; a guarda precisa recusar.
3. **Render ponta a ponta**: um vídeo sintético de 4 s com título, destaque, objeto 3D (render e extrusão), efeitos,
   legenda, vinheta, CTA e, na marca com música obrigatória, trilha da biblioteca. Mede loudness (−17 a −15 LUFS) e pico
   (< −1,5 dBFS) e confere o selo da marca no arquivo.

Termina em `TUDO OK` ou lista o que falhou. Mudança visual **intencional**: `editor.py testar --marca <marca> --atualizar`,
só na marca que mudou, e a folha nova entra no PR.

## CI

`.github/workflows/ci.yml` roda em todo PR e push na `main`: ruff, pytest, `biblioteca verificar`, baixa só a faixa usada
na regressão e roda `editor.py testar`. Se falhar, as folhas ficam como artefato do job.
