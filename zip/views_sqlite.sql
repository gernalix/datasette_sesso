DROP VIEW IF EXISTS "memento_v";
CREATE VIEW "memento_v" AS SELECT "id", "data", "durata" FROM "memento";

DROP VIEW IF EXISTS "come_viene_v";
CREATE VIEW "come_viene_v" AS SELECT "id", "come_viene" FROM "come_viene";

DROP VIEW IF EXISTS "cruising_v";
CREATE VIEW "cruising_v" AS SELECT "id", "inizio", "fine", "succhiati", "sborrano", "luogo_id" FROM "cruising";

DROP VIEW IF EXISTS "dove_sborra_v";
CREATE VIEW "dove_sborra_v" AS SELECT "id", "dove" FROM "dove_sborra";

DROP VIEW IF EXISTS "inattivo_v";
CREATE VIEW "inattivo_v" AS SELECT "id", "inattivo" FROM "inattivo";

DROP VIEW IF EXISTS "interrotto_v";
CREATE VIEW "interrotto_v" AS SELECT "id", "motivo" FROM "interrotto";

DROP VIEW IF EXISTS "io_sborro_v";
CREATE VIEW "io_sborro_v" AS SELECT "id", "sega_id", "sex_id" FROM "io_sborro";

DROP VIEW IF EXISTS "luogo_v";
CREATE VIEW "luogo_v" AS
SELECT "id", "indirizzo", "appartamento", "campanello",
       CASE WHEN "hotel" = 1 THEN '✅' ELSE '' END AS "hotel"
FROM "luogo";

DROP VIEW IF EXISTS "memento_sync_state_v";
CREATE VIEW "memento_sync_state_v" AS
SELECT "library_id", "last_revision" FROM "memento_sync_state";

DROP VIEW IF EXISTS "partner_v";
CREATE VIEW "partner_v" AS
SELECT "id",
       CASE WHEN "attivo" = 1 THEN '✅' ELSE '' END AS "attivo",
       "nome","cognome","nascita","patria_id","orientamento","xk_inattivo_id",
       CASE WHEN "catfish" = 1 THEN '✅' ELSE '' END AS "catfish",
       "ruolo",
       CASE WHEN "parco" = 1 THEN '✅' ELSE '' END AS "parco",
       CASE WHEN "grindr_screen" = 1 THEN '✅' ELSE '' END AS "grindr_screen",
       "grindr_nick","numero","facebook","instagram","indirizzo_id","note","logseq_id","preferenze",
       "bello","nick","razza_id","foto",
       CASE WHEN "logseq" = 1 THEN '✅' ELSE '' END AS "logseq",
       CASE WHEN "telegram" = 1 THEN '✅' ELSE '' END AS "telegram",
       "per_mese"
FROM "partner";

DROP VIEW IF EXISTS "patria_v";
CREATE VIEW "patria_v" AS SELECT "id","patria" FROM "patria";

DROP VIEW IF EXISTS "razza_v";
CREATE VIEW "razza_v" AS SELECT "id","razza" FROM "razza";

DROP VIEW IF EXISTS "sega_v";
CREATE VIEW "sega_v" AS
SELECT "id",
       CASE WHEN "dildo" = 1 THEN '✅' ELSE '' END AS "dildo",
       "quando"
FROM "sega";

DROP VIEW IF EXISTS "sesh_v";
CREATE VIEW "sesh_v" AS
SELECT "id","inizio","fine",
       CASE WHEN "pento" = 1 THEN '✅' ELSE '' END AS "pento",
       "olanze"
FROM "sesh";

DROP VIEW IF EXISTS "sex_v";
CREATE VIEW "sex_v" AS
SELECT "id","inizio","fine","partner_id","sesh_id","orgia_id","interrotto_id",
       CASE WHEN "droghe_offerte" = 1 THEN '✅' ELSE '' END AS "droghe_offerte",
       CASE WHEN "overdose" = 1 THEN '✅' ELSE '' END AS "overdose",
       CASE WHEN "mia_iniz" = 1 THEN '✅' ELSE '' END AS "mia_iniz",
       "gli_piacque","voto",
       CASE WHEN "video" = 1 THEN '✅' ELSE '' END AS "video",
       CASE WHEN "audio" = 1 THEN '✅' ELSE '' END AS "audio",
       CASE WHEN "lui_succhia" = 1 THEN '✅' ELSE '' END AS "lui_succhia",
       CASE WHEN "io_scopo" = 1 THEN '✅' ELSE '' END AS "io_scopo",
       CASE WHEN "io_succhio" = 1 THEN '✅' ELSE '' END AS "io_succhio",
       CASE WHEN "lui_scopa" = 1 THEN '✅' ELSE '' END AS "lui_scopa",
       CASE WHEN "bb" = 1 THEN '✅' ELSE '' END AS "bb",
       CASE WHEN "record" = 1 THEN '✅' ELSE '' END AS "record",
       CASE WHEN "lube" = 1 THEN '✅' ELSE '' END AS "lube",
       "luogo_id","logseq_id","libido",
       CASE WHEN "dom" = 1 THEN '✅' ELSE '' END AS "dom",
       CASE WHEN "dolore" = 1 THEN '✅' ELSE '' END AS "dolore",
       "dove_sborra_id","come_viene_id",
       CASE WHEN "chiacchiere" = 1 THEN '✅' ELSE '' END AS "chiacchiere",
       CASE WHEN "kink" = 1 THEN '✅' ELSE '' END AS "kink",
       CASE WHEN "viene_sega" = 1 THEN '✅' ELSE '' END AS "viene_sega",
       CASE WHEN "completo" = 1 THEN '✅' ELSE '' END AS "completo",
       CASE WHEN "fuori" = 1 THEN '✅' ELSE '' END AS "fuori",
       CASE WHEN "cruising" = 1 THEN '✅' ELSE '' END AS "cruising",
       "link","droghe"
FROM "sex";

DROP VIEW IF EXISTS "spatial_ref_sys_v";
CREATE VIEW "spatial_ref_sys_v" AS
SELECT "srid","auth_name","auth_srid","srtext","proj4text" FROM "spatial_ref_sys";

DROP VIEW IF EXISTS "spese_memento_v";
CREATE VIEW "spese_memento_v" AS
SELECT "memento_id","data","categoria","descrizione","importo","source_modified","raw"
FROM "spese_memento";
