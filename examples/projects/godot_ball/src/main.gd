extends Node2D
var position_x := 80.0
func _process(delta):
    position_x = fmod(position_x + 100 * delta, 720)
    queue_redraw()
func _draw():
    draw_circle(Vector2(position_x, 220), 30, Color.CORNFLOWER_BLUE)
