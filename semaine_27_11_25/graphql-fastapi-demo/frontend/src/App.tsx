import React from 'react';
import { ApolloProcvider } from '@apollo/client';
import { client } from './apollo/client';
import { UserList } from './components/UserList';
import './App.css';

function App() {
    return (
        <ApolloProcvider client={client}>
            <div className="App">
                <header className="App-header">
                    <h1>GraphQL FastAPI Demo</h1>
                </header>
                <main>
                    <UserList />
                </main>
            </div>
        </ApolloProcvider>
    );
}

export default App;