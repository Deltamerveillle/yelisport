create type public.registration_status as enum ('registered', 'cancelled');

create table public.events (
  id uuid primary key default extensions.gen_random_uuid(),
  sport_id uuid not null references public.sports(id) on delete restrict,
  organizer_id uuid not null references public.users(id) on delete cascade,
  title varchar(160) not null,
  description text,
  location varchar(240) not null,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  capacity integer not null check (capacity > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint events_date_order check (ends_at > starts_at)
);

create table public.event_registrations (
  id uuid primary key default extensions.gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  status public.registration_status not null default 'registered',
  registered_at timestamptz not null default now(),
  cancelled_at timestamptz,
  unique (event_id, user_id)
);

create index events_sport_starts_idx on public.events (sport_id, starts_at);
create index events_organizer_idx on public.events (organizer_id);
create index event_registrations_user_status_idx
on public.event_registrations (user_id, status);

create trigger events_set_updated_at before update on public.events
for each row execute function public.set_updated_at();

alter table public.events enable row level security;
alter table public.event_registrations enable row level security;

create policy "events_read_authenticated" on public.events for select to authenticated
using (true);
create policy "events_create_authenticated" on public.events for insert to authenticated
with check ((select auth.uid()) = organizer_id);
create policy "events_update_organizer" on public.events for update to authenticated
using ((select auth.uid()) = organizer_id) with check ((select auth.uid()) = organizer_id);

create policy "registrations_read_self" on public.event_registrations for select to authenticated
using ((select auth.uid()) = user_id);
create policy "registrations_create_self" on public.event_registrations for insert to authenticated
with check ((select auth.uid()) = user_id);
create policy "registrations_update_self" on public.event_registrations for update to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

grant select, insert, update on public.events to authenticated;
grant select, insert, update on public.event_registrations to authenticated;
