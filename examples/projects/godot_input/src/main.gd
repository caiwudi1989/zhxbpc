extends Node2D
var point:=Vector2(200,200)
func _process(delta):
    point+=Input.get_vector("ui_left","ui_right","ui_up","ui_down")*200*delta
    queue_redraw()
func _draw():
    draw_circle(point,20,Color.CORNFLOWER_BLUE)
