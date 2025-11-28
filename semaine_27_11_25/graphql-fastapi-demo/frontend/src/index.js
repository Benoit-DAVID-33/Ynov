import React from 'react';
import ReactDOM from 'react-dom/client';
import './App.css'; 
import App from './App'; 
import { ApolloClient, InMemoryCache, ApolloProvider } from '@apollo/client';

// 1. Configuration du client GraphQL (lien avec FastAPI)
const client = new ApolloClient({
  uri: 'http://127.0.0.1:8000/graphql', // L'adresse de ton backend
  cache: new InMemoryCache(),
});

// 2. Injection de React dans le HTML
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ApolloProvider client={client}>
      <App />
    </ApolloProvider>
  </React.StrictMode>
);