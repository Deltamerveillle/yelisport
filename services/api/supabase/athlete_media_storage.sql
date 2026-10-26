-- Apply to the SMS24 Supabase instance using the SQL editor.
-- Private bucket: direct uploads from client JWTs are FORBIDDEN.
-- The SMS24 backend checks ownership + subscription and issues a signed upload token.
-- Never grant public read access to unmoderated athlete content.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'sms24-athlete-media', 'sms24-athlete-media', false, 52428800,
  array['image/jpeg', 'image/png', 'image/webp', 'video/mp4']
)
on conflict (id) do nothing;

-- Remove any previous direct-upload policy. Signed server-granted uploads only.
drop policy if exists "SMS24 athlete media upload own prefix" on storage.objects;

-- Read and delete are restricted to the file owner; do not allow direct INSERT.
drop policy if exists "SMS24 athlete media read own prefix" on storage.objects;
create policy "SMS24 athlete media read own prefix"
on storage.objects for select to authenticated
using (
  bucket_id = 'sms24-athlete-media'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

drop policy if exists "SMS24 athlete media delete own prefix" on storage.objects;
create policy "SMS24 athlete media delete own prefix"
on storage.objects for delete to authenticated
using (
  bucket_id = 'sms24-athlete-media'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

-- No anonymous SELECT policy. Media remains private until moderated.
