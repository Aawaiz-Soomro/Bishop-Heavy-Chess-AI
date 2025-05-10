import chess
import math
import time
import sys
import csv
import unittest

BISHOP_HEAVY_FEN = "rbbqkbbn/pppppppp/8/8/8/8/PPPPPPPP/RBBQKBBN w Qq - 0 1"
PIECE_VALUES = {
    chess.PAWN:   1.0,
    chess.KNIGHT: 3.5,
    chess.BISHOP: 4.0,
    chess.ROOK:   6.0,
    chess.QUEEN:  9.0,
    chess.KING:   0.0
}
CENTER_SQUARES = [chess.D4, chess.D5, chess.E4, chess.E5]
BISHOP_PAIR_BONUS = 0.5
OPEN_FILE_BONUS = 0.25
SEMI_OPEN_FILE_BONUS = 0.10
BLOCKED_BISHOP_PENALTY = 0.2
KING_SAFETY_PENALTY = 0.5
KNIGHT_OUTPOST_BONUS = 0.1

ACCURACY_THRESHOLD = 0.70
node_count = 0

def evaluate_board(board):
    score = 0.0
    for p, v in PIECE_VALUES.items():
        score += len(board.pieces(p, chess.WHITE)) * v
        score -= len(board.pieces(p, chess.BLACK)) * v
    wm = len(list(board.legal_moves))
    board.push(chess.Move.null())
    bm = len(list(board.legal_moves))
    board.pop()
    score += 0.05 * (wm - bm)
    for sq in CENTER_SQUARES:
        pc = board.piece_at(sq)
        if pc:
            score += 0.20 if pc.color == chess.WHITE else -0.20
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        bishops = list(board.pieces(chess.BISHOP, color))
        if len(bishops) >= 2:
            score += sign * BISHOP_PAIR_BONUS
        for b in bishops:
            attacks = board.attacks(b)
            score += sign * 0.01 * len(attacks)
            if not attacks:
                score -= sign * BLOCKED_BISHOP_PENALTY
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        for r in board.pieces(chess.ROOK, color):
            f = chess.square_file(r)
            friendly = sum(1 for p in board.pieces(chess.PAWN, color) if chess.square_file(p) == f)
            enemy = sum(1 for p in board.pieces(chess.PAWN, not color) if chess.square_file(p) == f)
            if friendly == 0 and enemy == 0:
                score += sign * OPEN_FILE_BONUS
            elif friendly == 0 and enemy > 0:
                score += sign * SEMI_OPEN_FILE_BONUS
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        for n in board.pieces(chess.KNIGHT, color):
            if n in CENTER_SQUARES:
                score += sign * KNIGHT_OUTPOST_BONUS
    for color in [chess.WHITE, chess.BLACK]:
        km = board.king(color)
        if km is not None and board.is_attacked_by(not color, km):
            score += (-KING_SAFETY_PENALTY if color == chess.WHITE else KING_SAFETY_PENALTY)
    return score

def minimax(board, depth, alpha, beta, maximizing):
    global node_count
    node_count += 1
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)
    if maximizing:
        value = -math.inf
        for m in board.legal_moves:
            board.push(m)
            value = max(value, minimax(board, depth-1, alpha, beta, False))
            board.pop()
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value
    else:
        value = math.inf
        for m in board.legal_moves:
            board.push(m)
            value = min(value, minimax(board, depth-1, alpha, beta, True))
            board.pop()
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

def evaluate_and_predict(board, depth, gt_depth):
    global node_count
    node_count = 0
    start = time.time()
    white_to_move = (board.turn == chess.WHITE)
    best_value = -math.inf if white_to_move else math.inf
    alpha, beta = -math.inf, math.inf
    best_move = None
    for m in board.legal_moves:
        board.push(m)
        val = minimax(board, depth-1, alpha, beta, not white_to_move)
        board.pop()
        if white_to_move:
            if val > best_value:
                best_value, best_move = val, m
            alpha = max(alpha, best_value)
        else:
            if val < best_value:
                best_value, best_move = val, m
            beta = min(beta, best_value)
    pred_nodes = node_count
    pred_time = time.time() - start
    gt_move = None
    best_val = -math.inf if white_to_move else math.inf
    for m in board.legal_moves:
        board.push(m)
        val = minimax(board, gt_depth-1, -math.inf, math.inf, not white_to_move)
        board.pop()
        if white_to_move:
            if val > best_val:
                best_val, gt_move = val, m
        else:
            if val < best_val:
                best_val, gt_move = val, m
    return best_move, gt_move, pred_nodes, pred_time

def play_selfplay():
    depth = _ask_int("Enter search depth (e.g. 3): ")
    games = _ask_int("Number of self-play games: ")
    gt_depth = depth + 1
    stats = {'1-0':0, '0-1':0, '1/2-1/2':0}
    logs = []
    confusion = {}
    total_moves = 0
    correct_preds = 0
    total_nodes = 0
    total_time = 0.0
    for g in range(1, games+1):
        board = chess.Board(BISHOP_HEAVY_FEN)
        move_no = 1
        while not board.is_game_over():
            pmove, gtmove, nodes, tm = evaluate_and_predict(board, depth, gt_depth)
            correct = (pmove == gtmove)
            logs.append({
                'game': g,
                'move': move_no,
                'player': 'White' if board.turn else 'Black',
                'predicted': pmove.uci(),
                'ground_truth': gtmove.uci(),
                'correct': int(correct),
                'nodes': nodes,
                'time_s': f"{tm:.3f}"
            })
            key = (gtmove.uci(), pmove.uci())
            confusion[key] = confusion.get(key, 0) + 1
            total_moves += 1
            total_nodes += nodes
            total_time += tm
            correct_preds += (1 if correct else 0)
            board.push(pmove)
            move_no += 1
        stats[board.result()] += 1
    accuracy = correct_preds / total_moves
    print("\n=== Self-Play Summary ===")
    print("Results (W–L–D):", stats)
    print(f"Total moves: {total_moves:,} | Accuracy: {accuracy*100:.2f}%")
    if accuracy < ACCURACY_THRESHOLD:
        print(f"[!] Warning: accuracy below {ACCURACY_THRESHOLD*100:.0f}% threshold.")
    print(f"Avg nodes/move: {total_nodes/total_moves:,.1f}")
    print(f"Avg time/move: {total_time/total_moves*1000:.1f} ms")
    print("\nSample confusion entries (gt → pred : count):")
    for (gt, pr), cnt in list(confusion.items())[:10]:
        print(f"  {gt} → {pr} : {cnt}")
    with open('selfplay_stats.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=logs[0].keys())
        writer.writeheader()
        writer.writerows(logs)
    print("Detailed move logs written to selfplay_stats.csv")
    with open('confusion_matrix.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ground_truth', 'predicted', 'count'])
        for (gt, pr), cnt in confusion.items():
            writer.writerow([gt, pr, cnt])
    print("Full confusion matrix written to confusion_matrix.csv\n")
    sys.exit(0)

def _ask_int(prompt):
    while True:
        v = input(prompt).strip()
        if v.isdigit() and int(v) > 0:
            return int(v)
        print("Please enter a positive integer.")

def _ask_choice(prompt, choices):
    while True:
        c = input(prompt).strip().lower()
        if c in choices:
            return c
        print(f"Please enter one of {choices}.")

def main():
    menu = (
        "\n=== Bishop-Heavy Chess AI ===\n"
        "1) Human vs AI (single game)\n"
        "2) AI vs AI (self-play, with full logging)\n"
        "3) Exit\n"
    )
    while True:
        print(menu)
        choice = input("Select [1-3]: ").strip()
        if choice == '1':
            play_human_mode()
        elif choice == '2':
            play_selfplay()
        elif choice == '3':
            print("Goodbye!")
            break
        else:
            print("Invalid choice; please enter 1, 2, or 3.")

def play_human_mode():
    depth = _ask_int("Enter search depth (e.g. 3): ")
    color = _ask_choice("Play as white or black? (w/b): ", ['w','b'])
    play_single_human(depth, color)

def play_single_human(depth, human_color):
    board = chess.Board(BISHOP_HEAVY_FEN)
    human_white = (human_color == 'w')
    print(board, "\n")
    while not board.is_game_over():
        turn = "White" if board.turn else "Black"
        if (board.turn == chess.WHITE) == human_white:
            mv = input(f"{turn} to move (UCI): ").strip()
            try:
                move = chess.Move.from_uci(mv)
                if move in board.legal_moves:
                    board.push(move)
                else:
                    print("Illegal move.")
                    continue
            except:
                print("Bad UCI format.")
                continue
        else:
            print(f"{turn} (AI) thinking…")
            ai_move = find_best_move(board, depth)
            board.push(ai_move)
            print(f"{turn} plays {ai_move}")
        print(board, "\n")
    outcome = board.outcome(claim_draw=True)
    if outcome.winner is True:
        print("Checkmate! White wins.")
    elif outcome.winner is False:
        print("Checkmate! Black wins.")
    else:
        print(f"Game drawn by {outcome.termination.name.lower()}.")
    sys.exit(0)

def find_best_move(board, depth):
    global node_count
    best_move = None
    white_to_move = (board.turn == chess.WHITE)
    best_value = -math.inf if white_to_move else math.inf
    node_count = 0
    start = time.time()
    for m in board.legal_moves:
        board.push(m)
        val = minimax(board, depth-1, -math.inf, math.inf, not white_to_move)
        board.pop()
        if white_to_move:
            if val > best_value:
                best_value, best_move = val, m
        else:
            if val < best_value:
                best_value, best_move = val, m
    elapsed = time.time() - start
    print(f"  → nodes={node_count:,} time={elapsed:.2f}s eval={best_value:.2f}")
    return best_move

class VariantRuleTests(unittest.TestCase):
    def test_queenside_castling(self):
        board = chess.Board(BISHOP_HEAVY_FEN)
        self.assertIn(chess.Move.from_uci('e1c1'), board.legal_moves)
        self.assertNotIn(chess.Move.from_uci('e1g1'), board.legal_moves)
        self.assertIn(chess.Move.from_uci('e8c8'), board.legal_moves)
        self.assertNotIn(chess.Move.from_uci('e8g8'), board.legal_moves)

    def test_en_passant(self):
        fen = 'rbbqkbbn/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RBBQKBBN w Qq d6 0 3'
        board = chess.Board(fen)
        self.assertIn(chess.Move.from_uci('e5d6'), board.legal_moves)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        unittest.main(argv=[sys.argv[0]])
    else:
        main()
