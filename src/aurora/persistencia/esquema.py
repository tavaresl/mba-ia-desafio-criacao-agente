"""DDL do banco do domínio (idempotente)."""

__all__ = ["COMANDOS_ESQUEMA"]

COMANDOS_ESQUEMA: tuple[str, ...] = (
    "CREATE TABLE IF NOT EXISTS apartamentos (numero TEXT PRIMARY KEY, morador TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS areas (id TEXT PRIMARY KEY, nome TEXT NOT NULL, taxa TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS reservas (
        codigo TEXT PRIMARY KEY,
        apartamento TEXT NOT NULL REFERENCES apartamentos(numero),
        area_id TEXT NOT NULL REFERENCES areas(id),
        data TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('ativa', 'cancelada')),
        criada_em TEXT NOT NULL,
        cancelada_em TEXT
    )""",
    # G5: a exclusividade vale no instante da gravação, por restrição do próprio banco.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_reserva_ativa ON reservas(area_id, data) WHERE status = 'ativa'",
    """CREATE TABLE IF NOT EXISTS visitantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apartamento TEXT NOT NULL REFERENCES apartamentos(numero),
        nome TEXT NOT NULL,
        data TEXT NOT NULL,
        criado_em TEXT NOT NULL
    )""",
    "CREATE TABLE IF NOT EXISTS codigos_reserva (codigo TEXT PRIMARY KEY, emitido_em TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS sessoes (session_id TEXT PRIMARY KEY, apartamento TEXT NOT NULL, criada_em TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS metadados (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)",
)
