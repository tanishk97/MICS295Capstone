from flask import Flask, request, abort
from collections import defaultdict


app = Flask(__name__)

#counts the number of fork
def count_forks(board, player):
    count = 0
    for row in range(3):
        for col in range(3):
            if board[row][col] == ' ':
                board[row][col] = player
                if is_winning(board, player):
                    count += 1
                board[row][col] = ' '
    return count

#find if the next fork move actually exist and returns the first next fork move
def find_fork(board, player):
    for row in range(3):
        for col in range(3):
            if board[row][col] == ' ':
                board[row][col] = player
                if count_forks(board, player) > 1:
                    board[row][col] = ' '
                    return [row, col]
                board[row][col] = ' '
    return None

#checks if the player can win by just adding one 
def can_win(board, player):
    for row in range(3):
        for col in range(3):
            if board[row][col] == ' ':
                board[row][col] = player
                if is_winning(board, player):
                    board[row][col] = ' '
                    return [row, col]
                board[row][col] = ' '
    return None


#builds the board from 2d list to string
def build_string_from_2d_board(boardInListFormat):
    built_board_string = ""
    
    for i in range(3):
        for j in range(3):
            built_board_string+= boardInListFormat[i][j]
   
    return built_board_string

#builds the board from string to 2d list
def build_board_from_string(boardInStringFormat):
    built_board = [[' ' for x in range(3)]for y in range(3)]

    built_board[0][0] = boardInStringFormat[0]
    built_board[0][1] = boardInStringFormat[1]
    built_board[0][2] = boardInStringFormat[2]
    built_board[1][0] = boardInStringFormat[3]
    built_board[1][1] = boardInStringFormat[4]
    built_board[1][2] = boardInStringFormat[5]
    built_board[2][0] = boardInStringFormat[6]
    built_board[2][1] = boardInStringFormat[7]
    built_board[2][2] = boardInStringFormat[8]

    return built_board

#takes care of blocking the opponents fork
def block_fork(board):
    XFork = find_fork(board, 'x')
    if XFork:
        return XFork
    for row in range(3):
        for col in range(3):
            if board[row][col] == ' ':
                board[row][col] = 'o'
                if can_win(board, 'o'):
                    board[row][col] = ' '
                    return [row, col]
                board[row][col] = ' '
    return None


#plays on  the center when free
def play_center(board):
    if board[1][1] == ' ':
        return [1, 1]
    return None

#Plays on opposite side when opponent is there
def play_on_opposite_corner(board):
    if board[0][0] == 'x' and board[2][2] == ' ':
        return [2, 2]
    if board[2][2] == 'x' and board[0][0] == ' ':
        return [0, 0]
    if board[0][2] == 'x' and board[2][0] == ' ':
        return [2, 0]
    if board[2][0] == 'x' and board[0][2] == ' ':
        return [0, 2]
    return None


#validates the board that was given
def validate_board(stringBoard,tic_values):

    #checks if the values of the string are valid
    for x in tic_values:
        if x != 'x' and x != 'o' and x != ' ':
            return False
        
    #if there are too many characters or not enough return False
    if (tic_values['x'] + tic_values['o'] + tic_values[' '])!= 9:
        return False    

    #if there are extra x or o return False
    if tic_values['o'] == tic_values['x'] or tic_values['o']+1== tic_values['x'] :
        pass
    else:
        return False

    return True


#checks if a player is winning with the given positions
def is_winning(board, player):
    for row in range(3):
        if board[row][0] == board[row][1] == board[row][2] == player:
            return True  
    
    #checks columns
    for col in range(3):
        if board[0][col] == board[1][col] == board[2][col] == player:
            return True
    
    #check diagonals
    if board[0][0] == board[1][1] == board[2][2] == player:
        return True
    if board[0][2] == board[1][1] == board[2][0] == player:
        return True
    return False

#plays in first empty corner
def play_on_empty_corner(board):
    if board[0][0] == ' ':
        return [0, 0]
    if board[0][2] == ' ':
        return [0, 2]
    if board[2][0] == ' ':
        return [2, 0]
    if board[2][2] == ' ':
        return [2, 2]
    return None

#Play in first empty side
def play_on_empty_side(board):
    if board[0][1] == ' ':
        return [0, 1]
    if board[1][0] == ' ':
        return [1, 0]
    if board[1][2] == ' ':
        return [1, 2]
    if board[2][1] == ' ':
        return [2, 1]
    return None

#Main function that returns the output
@app.route('/',methods=['GET'])
def main():

    #gets the board as a string from the URL
    string_board = request.args.get('board', '')


    #calculates the number of X and O
    char_values = defaultdict(int)
    for char in string_board:
        char_values[char]+=1
        
    
    #validate the table
    valid_board = validate_board(string_board,char_values)
    
    if not valid_board:
        return abort(400)
    
    #builds the board from a string to 2d array
    tic_tac_toe_board= build_board_from_string(string_board)

    #checks if one of the players is winning before the next move
    #if one of them is winning before the next move it means the board is invalid they already won.
    IsXWinningAlready = is_winning(tic_tac_toe_board,'x')
    IsOWinningAlready = is_winning(tic_tac_toe_board,'o')
    
    if IsXWinningAlready or IsOWinningAlready:
        return abort(400)
    

    #1.check if player o can win with the next move
    canOwin = can_win(tic_tac_toe_board,'o')
    if canOwin:
        tic_tac_toe_board[canOwin[0]][canOwin[1]] = 'o'

        return build_string_from_2d_board(tic_tac_toe_board)
        #return board in string format


    
    #2.check if x needs to be blocked to avoid a win
    canXwin = can_win(tic_tac_toe_board,'x') 
    if canXwin:
        tic_tac_toe_board[canXwin[0]][canXwin[1]] = 'o'

        return build_string_from_2d_board(tic_tac_toe_board)
        #return board in string format

    #No need to block fork if there is less than two occurences of o
    if char_values['o']>1:
        #3.Check for fork moves
        forkForO = find_fork(tic_tac_toe_board,'o')
        if forkForO:
            tic_tac_toe_board[forkForO[0]][forkForO[1]] = 'o'

            return build_string_from_2d_board(tic_tac_toe_board)
            #return board in string format

   #No need to block fork if there is less than two occurences of x
    if char_values['x']>1:
        #4. Check if the opponent have forks and if they do block
        blockXfork = block_fork(tic_tac_toe_board)
        if blockXfork:
            tic_tac_toe_board[blockXfork[0]][blockXfork[1]] = 'o'

            return build_string_from_2d_board(tic_tac_toe_board)
            #return board in string format


    
    #5.Play center position
    center = play_center(tic_tac_toe_board)
    if center:
        tic_tac_toe_board[center[0]][center[1]] = 'o'

        return build_string_from_2d_board(tic_tac_toe_board)
        #return board in string format


    #6.Play opposite corner
    corner = play_on_empty_corner(tic_tac_toe_board)
    if corner:
        tic_tac_toe_board[corner[0]][corner[1]] = 'o'

        return build_string_from_2d_board(tic_tac_toe_board)
        #return board in string format

    #7.Play empty corner
    empty_corner = play_on_empty_corner(tic_tac_toe_board)
    if empty_corner:
        tic_tac_toe_board[empty_corner[0]][empty_corner[1]] = 'o'

        return build_string_from_2d_board(tic_tac_toe_board)
        #return board in string format


    #8.Play empty side
    empty_side = play_on_empty_side(tic_tac_toe_board)
    if empty_side:
        tic_tac_toe_board[empty_side[0]][empty_side[1]] = 'o'

        return build_string_from_2d_board(tic_tac_toe_board)
        #return board in string format

    return abort(400)


if __name__ == '__main__':
    app.run()