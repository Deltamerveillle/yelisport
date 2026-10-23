-- Apply to the SMS24 Supabase instance using the SQL editor.
-- Private bucket: signed-in athletes may upload only within their own user-id prefix.
-- Never grant public read access to unmoderated athlete content.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'sms24-athlete-media', 'sms24-athlete-media', false, 52428800,
  array['image/jpeg', 'image/png', 'image/webp', 'video/mp4']
)
on conflict (id) do nothing;

create policy "SMS24 athlete media upload own prefix"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'sms24-athlete-media'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

create policy "SMS24 athlete media read own prefix"
on storage.objects for select to authenticated
using (
  bucket_id = 'sms24-athlete-media'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

create policy "SMS24 athlete media delete own prefix"
on storage.objects for delete to authenticated
using (
  bucket_id = 'sms24-athlete-media'
  and (storage.foldername(name))[1] = (select auth.uid()::text)
);

-- No anonymous SELECT policy. Media remains private until moderated.
