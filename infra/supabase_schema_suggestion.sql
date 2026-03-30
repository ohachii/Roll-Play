-- Esboço de schema PostgreSQL/Supabase alinhado aos campos usados no Roll-Play (ficha JSON).
-- O projeto atual persiste fichas em arquivos JSON; use este script como base se migrar para Supabase.
-- Execute no SQL Editor do Supabase após revisar tipos e RLS.

create table if not exists characters (
  id uuid primary key default gen_random_uuid(),
  discord_user_id bigint not null,
  guild_id bigint,
  character_name text not null,
  system_rpg text default 'dnd',
  nivel_rank text,
  forca smallint,
  destreza smallint,
  constituicao smallint,
  inteligencia smallint,
  sabedoria smallint,
  carisma smallint,
  ca smallint,
  iniciativa text,
  hp_atual int,
  hp_max int,
  magia_atual int,
  magia_max int,
  spell_slots jsonb default '{}'::jsonb,
  salvaguardas_proficientes text[] default '{}',
  concentracao_magia text,
  condicoes text[] default '{}',
  sheet_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

create index if not exists idx_characters_discord on characters(discord_user_id);

comment on column characters.sheet_json is 'Documento completo da ficha (espelho do .json local) até a migração ser granular.';
comment on column characters.spell_slots is 'Ex.: {"1": {"max":4,"used":1}, "2": {"max":3,"used":0}}';
