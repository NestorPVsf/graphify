# Migración graphify fork v3 (0.3.28) → v8 (0.9.17)

> Rama de pruebas `v8-migration` (git worktree aislado). El checkout de producción
> `C:\Users\rotse\graphify-fork` permanece en `v3` — instalación editable intacta.
> Base: `upstream/v8` @ 43b2aff (0.9.17). Análisis: 2026-07-15.

## Corrección a la nota de decisión (2026-07-15)
La nota decía "47 commits propios". El dato real es **5 commits propios** sobre
`upstream/v3` (`git log upstream/v3..v3`). Los 3 fixes que la nota nombra están
entre esos 5. El "47" era una medición distinta (base equivocada).

## Veredicto de los 5 fixes propios contra v8

| Commit | Fix | Estado en v8 | Acción |
|---|---|---|---|
| `9ab1a21` | `GRAPH_REPORT.md` como UTF-8 en Windows | ✅ **RESUELTO** — v8 usa `encoding="utf-8"` en todos los `write_text` (`watch.py:1134` y resto) | Ninguna |
| `72b9913` (watch.py) | **preservar capa semántica en rebuild de código** (CRÍTICO) | ✅ **RESUELTO y SUPERIOR** — v8 preserva por *provenance/origin marker* + `_check_shrink` (shrink-guard). Documenta que filtrar por `file_type` (lo que hacía el fork) es incorrecto porque nodos INFERRED de código llevan `file_type="code"` (`watch.py:500-565`, `950-957`) | Ninguna — **validar empíricamente** |
| `d1474eb` | prefijo de IDs por path relativo (colisiones de stem, Next.js) | ✅ **RESUELTO nativo** — v8 usa el path repo-relativo completo como stem del ID + id-remap post-pass (`build.py:437-446`, `_make_id(str(path))` en `extract.py`). `ids.py` cita `#550 same-filename collisions` como resuelto | Ninguna |
| `72b9913` (validate.py) | aceptar file_types semánticos arbitrarios | ✅ **RESUELTO funcional** — v8 normaliza tipos desconocidos vía `_FILE_TYPE_SYNONYMS` → `concept` ANTES de validar, y el validate del build es **warning no-fatal** (`build.py:420-436`). No rompe ni pierde nodos | Ninguna funcional. **Matiz**: tipos custom (`normativa`, `decision`) colapsan a `concept` — pierden granularidad de tag Obsidian. → decisión Néstor |
| `5c9a2bd` | report: fallback a file nodes en comunidades sin non-file | 🟡 **COMPORTAMIENTO DISTINTO** — v8 *oculta* comunidades "thin" (solo-archivo) vía `min_community_size` + `continue` (`report.py:225-239`), decisión de diseño intencional | Cosmético del reporte. → decisión Néstor |

### Cambio de interfaz CLI (no es un fix, pero rompe flujo operativo)
- `172673f` añadió el comando propio **`graphify project-setup`** (hooks + `.graphifyignore` + sección CLAUDE.md en un paso). **v8 NO tiene ese comando.** v8 trae su propio sistema de setup (`install.py`, `skill-*.md`, CLI reescrito).
- **Acción Fase 3**: mapear el CLI de v8 y ver si `graphify install` (o equivalente) cubre lo mismo. Si sí → adoptar v8 y actualizar la skill/docs. Si no → portar `project-setup`.

## Conclusión del análisis
**Cero código propio que re-aplicar para funcionalidad.** Los 3 fixes técnicos
(UTF-8, capa semántica crítica, colisiones de IDs) están cubiertos en v8 de forma
nativa e igual o superior. Quedan **3 puntos de decisión operativa** (no bugs):
1. ¿Preservar tipos semánticos custom (`normativa`/`decision`) o aceptar el colapso a `concept`? (tags Obsidian)
2. ¿Mostrar comunidades solo-archivo en el reporte, o aceptar que v8 las oculte?
3. ¿`graphify project-setup` → adoptar el equivalente de v8 o portar el comando?

## Resultados Fase 3 — validación empírica (venv AISLADO, v8 0.9.17)
Entorno: venv `C:\Users\rotse\graphify-v8-testenv` (Python 3.14) con v8 editable. Proyecto
de prueba desechable con `alpha/handler.py` + `beta/handler.py` (mismo stem, a propósito).
**Aislamiento**: graphify NO está instalado como paquete en producción (no hay `.pth`/pip);
corre como `python -m graphify` desde el checkout. El venv separado lo aísla por completo.

- [x] **Colisiones de stem (d1474eb)** → ✅ RESUELTO EN v8. IDs `alpha_handler_*` vs `beta_handler_*`, sin colisión pese a compartir stem `handler`.
- [x] **UTF-8 (9ab1a21)** → ✅ RESUELTO. `GRAPH_REPORT.md` regenerado sin `UnicodeEncodeError`; todos los `write_text` usan `encoding="utf-8"`.
- [x] **Preservación de capa semántica (72b9913-watch, EL CRÍTICO)** → ✅ RESUELTO EN v8. Test: build de código → inyectar nodos concept/document/decision → tocar un `.py` + commit → `graphify update` (= rebuild del post-commit) → **los nodos semánticos SOBREVIVEN**. El bug catastrófico de la nota NO ocurre en v8.
  - ⚠️ Falso negativo detectado y corregido: v8 evicta nodos cuyo `source_file` no existe en disco (los trata como *fuente borrada*, `watch.py:477-493`). El primer test falló por inventar docs inexistentes; con docs reales en disco, preserva. En el flujo real los docs existen → OK.
- [x] **Tipos semánticos custom (72b9913-validate)** → ⚠️→✅ RE-APLICADO (Fase 2b). v8 colapsaba a `concept` cualquier `file_type` fuera de `{code,document,paper,image,rationale,concept}` (`build.py:420-422`, en CADA rebuild). Evidencia real (inspección de 6 grafos): **Gaea-Legal usa 29 nodos custom** (decision×17, normativa×7, technology×4, component×1, infrastructure×1). Los otros 5 proyectos solo usan canónicos. Néstor confirma que seguirá usando tipos ricos → fix re-aplicado (ver abajo).
- [ ] `graphify project-setup` (172673f): no existe en v8. Equivalente v8 = `graphify hook install` + `graphify claude install`. Falta decidir adoptar vs portar (Fase 4).
- [ ] Report fallback (5c9a2bd): cosmético, no probado a fondo. v8 oculta comunidades solo-archivo (`min_community_size`). Opcional.

### Veredicto de Fase 3
Migración viable como **reset limpio a upstream/v8 + 1 fix re-aplicado** (tipos custom).
Los 3 fixes técnicos ya venían cubiertos por upstream (2 verificados empíricamente, 1 por inspección).

## Fix aplicado (Fase 2b) — preservar tipos semánticos custom
Variante del fork fix `72b9913` adaptada a la reescritura de v8. Cambios en la rama:
- **`graphify/build.py`**: `_FILE_TYPE_SYNONYMS` reducido a solo normalizaciones de FORMATO
  (`markdown`/`text`→document, `tool`/`library`→code); se quitaron los mapeos que colapsaban
  semántica (`technology`/`framework`/`pattern`/`principle`/`constraint`/`tech`/`data-source`/`gotcha`→concept).
  El fallback del colapso pasó de `"concept"` a `ft` (preserva cualquier tipo desconocido tal cual).
- **`graphify/validate.py`**: `file_type` deja de ser allowlist estricto; acepta cualquier string no vacío.
- **Verificación empírica** (venv aislado, proyecto de prueba): inyectados 5 tipos de Gaea
  (normativa/decision/technology/component/infrastructure) → tras `graphify update` (rebuild post-commit)
  → **5/5 preservados con su tipo original** (no colapsados a `concept`). También confirma preservación semántica.
- Estos 2 archivos quedan MODIFICADOS en el working tree del worktree, **sin commitear** (pendiente OK de Néstor).

## Fase 4 (NO en esta sesión)
Cambiar la instalación editable de producción de v3 a v8 — solo tras aprobación explícita.
El usuario pidió únicamente rama de pruebas. Antes de Fase 4, conviene:
1. Commit del fix de tipos custom en la rama `v8-migration`.
2. Segunda opinión cross-model (Codex) del fix, por protocolo.
3. Decidir `project-setup` (adoptar comandos v8 vs portar) y actualizar la skill graphify a la de v8.
4. Migración de datos: el primer `update` bajo v8 en cada proyecto re-tipa/reconstruye; en Gaea, validar que los 29 nodos custom sobreviven en el grafo REAL (no solo el de prueba).

## Fase 4 (NO en esta sesión)
Cambiar la instalación editable de producción de v3 a v8 — solo tras Fase 3 verde
y aprobación explícita. El usuario pidió únicamente rama de pruebas.
