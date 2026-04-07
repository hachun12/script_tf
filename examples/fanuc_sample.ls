/PROG PICK_PLACE
/ATTR
/MN
! 設定工具與座標系
UTOOL_NUM=1
UFRAME_NUM=0
! 移動到安全位置
J P[1] 50% FINE
! 接近取料點
L P[2] 500mm/sec CNT50
L P[3] 200mm/sec FINE
! 夾取工件
DO[1]=ON
WAIT 0.5(sec)
! 確認夾取
WAIT DI[1]=ON
! 抬起
L P[4] 300mm/sec FINE
! 移動到放料位置
J P[5] 80% CNT30
L P[6] 200mm/sec FINE
! 放開工件
DO[1]=OFF
WAIT 0.3(sec)
! 退回安全位置
L P[7] 500mm/sec CNT50
J P[1] 50% FINE
/END
