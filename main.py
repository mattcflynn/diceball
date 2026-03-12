from game.engine import play_at_bat, get_validated_input

def main():
    """Main function to run the Diceball game."""

    pitcher_choice = get_validated_input("Play against [h]uman or [c]pu pitcher? ", ['h', 'c'])
    pitcher_is_ai = pitcher_choice == 'c'

    hitter_choice = get_validated_input("Play as [h]uman or [c]pu hitter? ", ['h', 'c'])
    hitter_is_ai = hitter_choice == 'c'

    while True:
        try:
            pitcher_dice_count_str = get_validated_input("Enter the number of dice for the pitcher (4 or 5): ", ['4','5'])
            play_at_bat(int(pitcher_dice_count_str), pitcher_is_ai, hitter_is_ai)
        except ValueError:
            print("Invalid input. Please enter a number.")

        play_again = get_validated_input("\nPlay another at-bat? [y]es or [n]o: ", ['y', 'n'])
        if play_again == 'n':
            print("Thanks for playing!")
            break

if __name__ == "__main__":
    main()

