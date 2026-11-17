# Tp - Introduction à Triton Inference Server

## Partie 1 - Découvrir Triton

---
**NOTE**
L'objectif de cette partie est de vous familiariser avec l'outil. Nous utiliserons des modèles pré-entraînés et mis à disposition par Nvidia pour commencer.
*Dans la mesure du possible utilisez Ubuntu via wsl pour faire ce tp.*

----
1/ Cloner le répo officiel : https://github.com/triton-inference-server/server.git.
Nous commencerons par suivre la documentation sur la construction d'un docker utilisant mis à disposition via le script bash ./server/docs/examples/fetch_models.sh. 

2/ Choissisez une version d'image triton. Récuperez là puis lancez un container avec un server triton manageant la totalité des modèles proposés par Nvidia.

  docker run --gpus=1 --rm -p8000:8000 -p8001:8001 -p8002:8002 -v/full/path/to/docs/examples/model_repository:/models nvcr.io/nvidia/tritonserver:<xx.yy>-py3 tritonserver --model-repository=/models

ex:

  docker run --rm -p8000:8000 -p8001:8001 -p8002:8002 -v<FULL PATH HERE>/server/docs/examples/model_repository:/models nvcr.io/nvidia/tritonserver:22.01-py3 tritonserver --model-repository=/models

3/ Vérifiez que votre server is up and running : Inspectez les logs du container pour voir quels sont les éléments utilisez curl et le port HTTP pour vérifiez l'état de votre serveur.

4/ Inspectez le contenu du dossier contenant le modèle densenet_onnx : cette infrastructure est essentielle au bon fonctionnement de Triton. 
![Architecture model triton](./img/archi_triton.png)

* le fichier config.pbtxt permet de spécifier le comportement du modèle:
    * nom du modèle 
    * type de backend utilisé
    * taille de batch
    * contrat d'interface pour les données passées au modèle: nom/ type/ dimensions etc
    * contrat d'interface pour la sortie: spécification du retour du modèle

Pour construire votre propre modèle et le servir via triton vous aurez donc besoin de construire ce fichier et de fournir tous les éléments nécessaires à triton pour qu'il puisse tourner. Pour plus d'information consultez cette [documentation](https://github.com/triton-inference-server/server/blob/r22.01/docs/model_configuration.md).

---
## Partie 2 - Créer un client - Intégration

1/ Récupérer le script client proposée par Nvidia [ici](https://github.com/triton-inference-server/tutorials/tree/main/Quick_Deploy/ONNX)

2/ Faites le fonctionner ! Attention à la dimension de batch : si le serveur n'attend pas de dimension de batch, n'en mettez pas.

4/ Regardez les différents exemples de clients disponibles par uses cases : 
  https://github.com/triton-inference-server/client/tree/main/src/python/examples

5/ Transformer votre client en asynchrone en vous inspirant des autres examples
  Vous avez un client performant prêt à être intégré dans une api back !

---
## Ressources complémentaires 
![Characteristics grpc](./img/grpc_spec.png)

[Source](https://learn.microsoft.com/en-us/aspnet/core/grpc/comparison?view=aspnetcore-7.0)
* Configuration des modèles : 
    * https://github.com/triton-inference-server/server/blob/r22.01/docs/model_configuration.md
* Documentation pour la librairie cliente :
    * https://github.com/triton-inference-server/client
    * https://github.com/triton-inference-server/client#image-classification-example
    * https://github.com/triton-inference-server/client/blob/main/src/python/examples/simple_http_infer_client.py
    * https://github.com/triton-inference-server/client/blob/main/src/python/examples/image_client.py
* Documentation pour la gestion des backends: 
    * doc générale : https://github.com/triton-inference-server/backend
    * exemples : https://github.com/triton-inference-server/backend/blob/main/examples/README.md 

* Gestion d'un backend python : modèles développés en python https://github.com/triton-inference-server/python_backend#user-documentation


