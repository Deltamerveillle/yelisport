create extension if not exists pgcrypto with schema extensions;

create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.profiles (
  user_id uuid primary key references public.users(id) on delete cascade,
  display_name varchar(80),
  first_name varchar(80),
  last_name varchar(80),
  birth_date date,
  avatar_url text,
  locale varchar(10) not null default 'fr',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.sports (
  id uuid primary key default extensions.gen_random_uuid(),
  slug varchar(80) not null unique,
  name varchar(120) not null,
  description text,
  icon_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index users_email_idx on public.users (lower(email));
create index sports_active_name_idx on public.sports (name) where is_active;

create function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger users_set_updated_at before update on public.users
for each row execute function public.set_updated_at();
create trigger profiles_set_updated_at before update on public.profiles
for each row execute function public.set_updated_at();
create trigger sports_set_updated_at before update on public.sports
for each row execute function public.set_updated_at();

create function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.users (id, email)
  values (new.id, coalesce(new.email, new.id::text));
  insert into public.profiles (user_id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'display_name');
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

alter table public.users enable row level security;
alter table public.profiles enable row level security;
alter table public.sports enable row level security;

create policy "users_read_self" on public.users for select
using ((select auth.uid()) = id);
create policy "profiles_read_self" on public.profiles for select
using ((select auth.uid()) = user_id);
create policy "profiles_update_self" on public.profiles for update
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "sports_read_authenticated" on public.sports for select to authenticated
using (is_active);

grant select on public.users, public.profiles, public.sports to authenticated;
grant update (display_name, first_name, last_name, birth_date, avatar_url, locale)
on public.profiles to authenticated;

insert into public.sports (slug, name, description) values
  ('football', 'Football', 'Football association'),
  ('basketball', 'Basketball', 'Basketball'),
  ('athletics', 'Athlétisme', 'Courses, sauts et lancers')
on conflict (slug) do nothing;
