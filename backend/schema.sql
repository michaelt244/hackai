-- Run this in your Butterbase dashboard SQL editor

create table if not exists channel_usage (
  id bigserial primary key,
  channel_id text not null,
  cost_cents float not null,
  created_at timestamptz default now()
);

create table if not exists channel_summaries (
  id bigserial primary key,
  channel_id text not null,
  summary_date date not null default current_date,
  summary_text text not null,
  created_at timestamptz default now(),
  unique(channel_id, summary_date)
);

create table if not exists contacts (
  id bigserial primary key,
  channel_id text not null,
  name text,
  company text,
  role text,
  context text,
  action_items jsonb,
  sentiment text,
  follow_up_date timestamptz,
  created_at timestamptz default now()
);

create index if not exists idx_channel_usage_channel on channel_usage(channel_id);
create index if not exists idx_channel_summaries_channel on channel_summaries(channel_id);
create index if not exists idx_contacts_channel on contacts(channel_id);
