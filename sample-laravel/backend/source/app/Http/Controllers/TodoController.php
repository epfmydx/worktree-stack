<?php

namespace App\Http\Controllers;

use App\Models\Todo;
use Illuminate\Http\Request;

class TodoController extends Controller
{
    public function index()
    {
        $todos = Todo::orderByDesc('id')->get();
        return view('todos', ['todos' => $todos]);
    }

    public function store(Request $request)
    {
        $data = $request->validate(['text' => 'required|string|max:255']);
        Todo::create(['text' => $data['text']]);
        return redirect('/');
    }

    public function destroy(Todo $todo)
    {
        $todo->delete();
        return redirect('/');
    }
}
