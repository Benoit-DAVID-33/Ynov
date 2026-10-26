import java.util.LinkedList;
import java.util.Queue;

public class FileAttente {
    public static void main(String[] args) {
        Queue<String> file = new LinkedList<>();

        // Ajout d'éléments dans la file
        file.add("Alice");
        file.add("Bob");
        file.add("Charlie");

        // Traitement de la file
        while (!file.isEmpty()) {
            String personne = file.poll(); // retire et retourne l'élément en tête
            System.out.println("Traitement de : " + personne);
        }
    }
}