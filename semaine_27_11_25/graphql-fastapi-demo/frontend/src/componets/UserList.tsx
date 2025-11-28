import React, { useState } from 'react';
import { useQuery, useMutation, gql } from '@apollo/client';

// --- Définition des requêtes GraphQL ---

const GET_USERS = gql`
  query GetUsers($filter: UserFilter, $skip: Int, $limit: Int) {
    users(filter: $filter, skip: $skip, limit: $limit) {
      id
      name
      email
    }
  }
`;

const CREATE_USER = gql`
  mutation CreateUser($userInput: UserInput!) {
    createUser(userInput: $userInput) {
      id
      name
      email
    }
  }
`;

const UPDATE_USER = gql`
  mutation UpdateUser($id: Int!, $userInput: UserInput!) {
    updateUser(id: $id, userInput: $userInput) {
      id
      name
      email
    }
  }
`;

const DELETE_USER = gql`
  mutation DeleteUser($id: Int!) {
    deleteUser(id: $id)
  }
`;

// --- Composant React ---

export const UserList: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [editingUser, setEditingUser] = useState<any>(null);

  // Hook de lecture (Query)
  const { loading, error, data, refetch } = useQuery(GET_USERS, {
    variables: {
      filter: searchTerm ? { name: searchTerm } : undefined,
      limit: 50
    }
  });

  // Hook de création
  const [createUser] = useMutation(CREATE_USER, {
    onCompleted: () => {
      setName('');
      setEmail('');
      refetch();
    }
  });

  // Hook de modification
  const [updateUser] = useMutation(UPDATE_USER, {
    onCompleted: () => {
      setEditingUser(null);
      refetch();
    }
  });

  // Hook de suppression
  const [deleteUser] = useMutation(DELETE_USER, {
    onCompleted: () => refetch()
  });

  // Gestion de la soumission du formulaire (Ajout ou Edition)
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingUser) {
      updateUser({
        variables: {
          id: editingUser.id,
          userInput: { name, email }
        }
      });
    } else {
      createUser({
        variables: {
          userInput: { name, email }
        }
      });
    }
  };

  // Préparer le formulaire pour l'édition
  const handleEdit = (user: any) => {
    setEditingUser(user);
    setName(user.name);
    setEmail(user.email);
  };

  // Annuler l'édition
  const handleCancel = () => {
    setEditingUser(null);
    setName('');
    setEmail('');
  };

  // Gestion de la recherche
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    refetch({
      filter: searchTerm ? { name: searchTerm } : undefined
    });
  };

  if (loading) return <div className="loading">Chargement...</div>;
  if (error) return <div className="error">Erreur : {error.message}</div>;

  return (
    <div className="user-management">
      <h2>Gestion des Utilisateurs</h2>

      {/* Formulaire de recherche */}
      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          placeholder="Rechercher par nom..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <button type="submit">Rechercher</button>
        <button
          type="button"
          onClick={() => {
            setSearchTerm('');
            refetch({ filter: undefined });
          }}
        >
          Effacer
        </button>
      </form>

      {/* Formulaire de création / édition */}
      <form onSubmit={handleSubmit} className="user-form">
        <h3>{editingUser ? 'Modifier' : 'Ajouter'} un utilisateur</h3>
        <div className="form-group">
          <input
            type="text"
            placeholder="Nom"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="form-actions">
          <button type="submit">
            {editingUser ? 'Modifier' : 'Créer'} Utilisateur
          </button>
          {editingUser && (
            <button type="button" onClick={handleCancel}>
              Annuler
            </button>
          )}
        </div>
      </form>

      {/* Liste des utilisateurs */}
      <div className="user-list">
        <h3>Liste des Utilisateurs ({data?.users.length})</h3>
        {data?.users.map((user: any) => (
          <div key={user.id} className="user-card">
            <div className="user-info">
              <strong>{user.name}</strong>
              <span className="user-email">{user.email}</span>
            </div>
            <div className="user-actions">
              <button onClick={() => handleEdit(user)}>
                Modifier
              </button>
              <button
                onClick={() => {
                  if (window.confirm('Supprimer cet utilisateur ?')) {
                    deleteUser({ variables: { id: user.id } });
                  }
                }}
                className="delete-btn"
              >
                Supprimer
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};