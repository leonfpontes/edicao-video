"""Peças do render: divisão em trechos paralelos, caminhos relativos ao EDL e LUTs de cor."""
import numpy as np

from motor.cor import aplicar_cor, lut_cor
from motor.renderizar import caminho_edl, dividir_trechos, resolver_caminhos


def segs(*ns):
    return [{"n": n} for n in ns]


def test_trechos_cobrem_tudo_em_ordem():
    for lst in (segs(90), segs(30, 30, 30, 30, 30, 30), segs(200, 10, 10, 10, 300, 45)):
        for n in (1, 2, 4, 12):
            g = dividir_trechos(lst, n)
            assert g[0][0] == 0 and g[-1][1] == len(lst)
            assert all(a[1] == b[0] for a, b in zip(g, g[1:]))
            assert len(g) <= n


def test_trechos_nao_ficam_curtos_demais():
    assert len(dividir_trechos(segs(10, 10, 10), 8)) == 1  # 1 s de vídeo não vale vários processos


def test_caminhos_relativos_a_pasta_do_edl(tmp_path):
    (tmp_path / "tela.png").write_bytes(b"x")
    assert caminho_edl("tela.png", tmp_path) == str(tmp_path / "tela.png")
    assert caminho_edl("id-da-biblioteca", tmp_path) == "id-da-biblioteca"
    assert caminho_edl("/abs/x.mp4", tmp_path) == "/abs/x.mp4"
    edl = resolver_caminhos({"elementos": [{"tipo": "broll", "arquivo": "tela.png"}]}, tmp_path)
    assert edl["elementos"][0]["arquivo"] == str(tmp_path / "tela.png")


def test_lut_de_cor_igual_ao_calculo_canal_a_canal():
    c = {"contraste": 1.1, "calor": 0.05}
    f = np.random.default_rng(0).integers(0, 255, (40, 30, 3), np.uint8)
    x = np.arange(256, dtype=np.float32)
    y = (x - 128) * 1.1 + 128
    ref = np.stack([np.clip(y * 0.95, 0, 255).astype(np.uint8)[f[..., 0]], np.clip(y, 0, 255).astype(np.uint8)[f[..., 1]],
                    np.clip(y * 1.05, 0, 255).astype(np.uint8)[f[..., 2]]], -1)
    assert np.array_equal(aplicar_cor(f, lut_cor(c), c), ref)


def test_lut3d_identidade_e_inversao(tmp_path):
    from motor.cor import aplicar_lut3d, ler_cube, tabela_lut3d
    n = 9
    linhas = ["TITLE \"teste\"", f"LUT_3D_SIZE {n}"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                linhas.append(f"{r / (n - 1):.6f} {g / (n - 1):.6f} {b / (n - 1):.6f}")
    (tmp_path / "id.cube").write_text("\n".join(linhas))
    f = np.random.default_rng(1).integers(0, 255, (30, 20, 3), np.uint8)
    tab = tabela_lut3d(ler_cube(tmp_path / "id.cube"))
    assert np.abs(aplicar_lut3d(f, tab).astype(int) - f).max() <= 2  # 128 níveis: erro de no máximo 2
    inv = linhas[:2] + [" ".join(f"{1 - float(v):.6f}" for v in li.split()) for li in linhas[2:]]
    (tmp_path / "inv.cube").write_text("\n".join(inv))
    out = aplicar_lut3d(f, tabela_lut3d(ler_cube(tmp_path / "inv.cube")))
    assert np.abs(out.astype(int) - (255 - f)).max() <= 3
    meio = aplicar_lut3d(f, tabela_lut3d(ler_cube(tmp_path / "inv.cube"), 0.5))
    assert np.abs(meio.astype(int) - 127).max() <= 3


def test_pele_protegida():
    from motor.cor import mascara_pele, proteger_pele
    pele = np.zeros((80, 80, 3), np.uint8)
    pele[:] = (120, 150, 210)  # BGR de um tom de pele
    pele[:, 40:] = (200, 120, 40)  # azul, fora da pele
    m = mascara_pele(pele)
    assert m[40, 10, 0] > 0.8 and m[40, 70, 0] < 0.1
    tratado = np.full_like(pele, 255)
    out = proteger_pele(pele, tratado)
    assert out[40, 10].mean() < 220 and out[40, 70].mean() > 250


def test_igualar_clipes_aproxima_a_cor(tmp_path):
    import cv2

    from motor.cor import igualar_clipes, lut_clipe
    arq = tmp_path / "v.mp4"
    vw = cv2.VideoWriter(str(arq), cv2.VideoWriter_fourcc(*"mp4v"), 30, (96, 170))
    rng = np.random.default_rng(0)
    for k in range(60):
        base = rng.integers(60, 140, (170, 96, 3)).astype(np.uint8)
        vw.write(base if k < 30 else cv2.add(base, (50, 10, 0, 0)))  # 2º clipe mais azul
    vw.release()
    cc = igualar_clipes(arq, [{"ini": 0, "fim": 1}, {"ini": 1, "fim": 2}])
    assert cc and len(cc) == 2
    lut = lut_clipe(cc[1])
    assert lut[0, 150, 0] < 150  # o azul do 2º clipe desce
