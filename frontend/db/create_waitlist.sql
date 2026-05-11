-- 1. Create the waitlist table with analytics fields
create table public.waitlist (
  id uuid default gen_random_uuid() primary key,
  email text not null unique,
  status text not null default 'pending', -- e.g., 'pending', 'delivered', 'failed'
  app_step text not null default 'alpha_version',
  user_agent text,
  referrer text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 2. Grant table permissions to anon role
GRANT INSERT, UPDATE ON public.waitlist TO anon;

-- 3. Enable Row-Level Security (RLS)
alter table public.waitlist enable row level security;

-- 4. Create policies for the anon role
create policy "Allow anonymous inserts"
on public.waitlist
for insert
to anon
with check (true);

-- Allow blind updates (so the server can update status to 'delivered' via anon key)
create policy "Allow anonymous updates"
on public.waitlist
for update
to anon
using (true);
