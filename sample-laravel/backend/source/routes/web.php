<?php

use App\Http\Controllers\TodoController;
use Illuminate\Support\Facades\Route;

Route::get('/',         [TodoController::class, 'index']);
Route::post('/',        [TodoController::class, 'store']);
Route::delete('/{todo}',[TodoController::class, 'destroy']);
