<?php

namespace Tests\Feature;

use App\Models\Todo;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ExampleTest extends TestCase
{
    use RefreshDatabase;

    public function test_the_todo_page_returns_a_successful_response(): void
    {
        $response = $this->get('/');

        $response->assertStatus(200);
        $response->assertSee('(no todos yet)');
    }

    public function test_a_todo_can_be_created_listed_and_deleted(): void
    {
        $this->post('/', ['text' => 'Disposable CI task'])->assertRedirect('/');
        $todo = Todo::sole();
        $this->assertSame('Disposable CI task', $todo->text);
        $this->get('/')->assertSee('Disposable CI task');
        $this->delete('/'.$todo->id)->assertRedirect('/');
        $this->assertDatabaseCount('todos', 0);
    }

    public function test_empty_or_oversized_todos_are_rejected(): void
    {
        foreach (['', str_repeat('x', 256)] as $text) {
            $this->post('/', ['text' => $text])->assertSessionHasErrors('text');
        }
        $this->assertDatabaseCount('todos', 0);
    }

    public function test_deleting_a_missing_todo_returns_not_found(): void
    {
        $this->delete('/999999')->assertNotFound();
    }
}
