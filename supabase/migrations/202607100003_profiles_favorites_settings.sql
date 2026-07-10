alter table public.profiles
  add column biography text,
  add column city varchar(120),
  add column country varchar(120);

create table public.user_settings (
  user_id uuid primary key references public.users(id) on delete cascade,
  language varchar(10) not null default 'fr',
  dark_mode boolean not null default false,
  notifications_enabled boolean not null default true,
  updated_at timestamptz not null default now()
);

create table public.favorite_sports (
  id uuid primary key default extensions.gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  sport_id uuid not null references public.sports(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, sport_id)
);

create table public.favorite_events (
  id uuid primary key default extensions.gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, event_id)
);

create index favorite_sports_user_idx on public.favorite_sports (user_id);
create index favorite_events_user_idx on public.favorite_events (user_id);

create trigger user_settings_set_updated_at before update on public.user_settings
for each row execute function public.set_updated_at();

alter table public.user_settings enable row level security;
alter table public.favorite_sports enable row level security;
alter table public.favorite_events enable row level security;

create policy "settings_self" on public.user_settings for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "favorite_sports_self" on public.favorite_sports for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "favorite_events_self" on public.favorite_events for all to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.user_settings to authenticated;
grant select, insert, delete on public.favorite_sports, public.favorite_events to authenticated;
grant update (display_name, first_name, last_name, birth_date, avatar_url, biography, city, country, locale)
on public.profiles to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('avatars', 'avatars', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

create policy "avatar_read_public" on storage.objects for select
using (bucket_id = 'avatars');
create policy "avatar_insert_self" on storage.objects for insert to authenticated
with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "avatar_update_self" on storage.objects for update to authenticated
using (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.users (id, email)
  values (new.id, coalesce(new.email, new.id::text));
  insert into public.profiles (user_id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'display_name');
  insert into public.user_settings (user_id) values (new.id);
  return new;
end;
$$;

insert into public.user_settings (user_id)
select id from public.users
on conflict (user_id) do nothing;
