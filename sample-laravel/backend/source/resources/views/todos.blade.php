<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>sample-laravel todos</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 3rem auto; padding: 0 1rem; }
  form.add { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  form.add input { flex: 1; padding: 0.4rem; }
  ul { list-style: none; padding: 0; }
  li { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #eee; }
  button { cursor: pointer; }
</style>
</head>
<body>
<h1>sample-laravel todos</h1>
<p style="color:#666">Pattern 1: PHP/Laravel monolith &mdash; MySQL on dev-db-net, served via gateway wildcard vhost.</p>

<form class="add" method="post" action="/">
  @csrf
  <input name="text" placeholder="Add a todo..." required maxlength="255" autofocus>
  <button type="submit">Add</button>
</form>

<ul>
@forelse($todos as $todo)
  <li>
    <span>{{ $todo->text }}</span>
    <form method="post" action="/{{ $todo->id }}">@csrf @method('DELETE')
      <button type="submit">delete</button>
    </form>
  </li>
@empty
  <li style="color:#999">(no todos yet)</li>
@endforelse
</ul>
</body>
</html>
