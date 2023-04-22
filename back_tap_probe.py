# Back Tap Probe Processes

from . import probe


class BackTapProbe(probe.PrinterProbe):
    def __init__(self, config, mcu_probe):
        super().__init__(config, mcu_probe)
        self.config = config
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.use_deviation = config.getboolean('use_deviation')
        self.xz_deviation_min = config.getfloat('deviation_min_x')
        self.xz_deviation_max = config.getfloat('deviation_max_x')
        self.x_deviation_min_pos = config.getfloat('deviation_min_x_pos')
        self.x_deviation_max_pos = config.getfloat('deviation_max_x_pos')
        self.x_home = config.getfloat('home_x_pos')
        self.deviation_debug = config.getboolean('visualize_deviation', False)

    def process_deviation(self, pos):
        if (self.use_deviation):
            # Safety check for 0
            if pos[0] == self.x_home:
                z_deviation = 0
            elif pos[0] > self.x_home:
                # Calculate positive deviation
                z_deviation = self.xz_deviation_max*(pos[0]-self.x_home)/(self.x_deviation_max_pos-self.x_home)
            else:
                # Calculate negative deviation
                z_deviation = self.xz_deviation_min*(self.x_home-pos[0])/(self.x_home-self.x_deviation_min_pos)
            # Print New Z values with Deviation
            self.gcode.respond_info("XZ deviation calculated at %.6f, Old Z=%.6f, New Z=%.6f"
                                    % (z_deviation, pos[2], pos[2]+z_deviation))
            # update z offset with deviation
            if (self.deviation_debug):
                pos[2]=z_deviation
            else:
                pos[2]+=z_deviation
        return pos[:3]
    # 
    def _probe(self, speed):
        pos = super()._probe(speed)
        pos = self.process_deviation(pos)
        return pos
        

class BackTapCalibration:
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.speed = config.getfloat('speed', 5.0, above=0.)
        self.use_deviation = config.getboolean('use_deviation')
        self.xz_deviation_min = config.getfloat('deviation_min_x')
        self.xz_deviation_max = config.getfloat('deviation_max_x')
        self.x_deviation_min_pos = config.getfloat('deviation_min_x_pos')
        self.x_deviation_max_pos = config.getfloat('deviation_max_x_pos')
        self.x_home = config.getfloat('home_x_pos')
        self.deviation_debug = config.getboolean('visualize_deviation', False)
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_move = self.printer.load_object(config, "gcode_move")
        self.gcode.register_command("BACK_TAP_CALIBRATE", self.cmd_BACK_TAP_CALIBRATE, desc=self.cmd_BACK_TAP_CALIBRATE_help)
        self.gcode.register_command("BACK_TAP_MOVE", self.cmd_BACK_TAP_MOVE, desc=self.cmd_BACK_TAP_MOVE_help)
        self.calibration_y = config.getfloat('home_y_pos')
        self.calibration_speed = config.getfloat('calibration_speed')
        self.calibration_lift_speed = config.getfloat('calibration_lift_speed')
        self.samples = config.getint('calibration_samples', 1, minval=1)
        points = self._generate_points()
        self.probe_helper = probe.ProbePointsHelper(self.config,
                                            self.probe_finalize,
                                            default_points=points)
        self.probe_helper.minimum_points(3)
        self.probe_helper.speed = self.calibration_speed
        self.pseudo_mesh=[]

    def _generate_points(self):
        y=self.calibration_y
        xmin = self.x_deviation_min_pos
        xmax = self.x_deviation_max_pos
        home = self.x_home
        points = [[xmin,y],[(home+xmin)/2,y],[home,y],[(home+xmax)/2,y],[xmax,y]]
        return points

    def cmd_BACK_TAP_CALIBRATE(self, gcmd):
        self.gcode.respond_info("Starting Back Tap Probe Calibration: Probing...")
        prnt_probe = self.printer.lookup_object('probe', None)
        # Init probe settings
        def_use_deviation = self.use_deviation
        def_probe_samples = prnt_probe.sample_count
        self.use_deviation = False
        prnt_probe.sample_count = self.samples
        # Run probing
        self.probe_helper.start_probe(gcmd)
        # Restore settings
        self.use_deviation = def_use_deviation
        prnt_probe.sample_count =  def_probe_samples

    cmd_BACK_TAP_CALIBRATE_help = "Calibrate min and max probe deviation"

    def probe_finalize(self, offsets, positions):
        self.gcode.respond_info("Gathering probe data...")
        z = []
        for i in positions:
            z_new=round(i[2],3)
            z.append(z_new)
        self.gcode.respond_info("Absolute Z positions: %s"
                                    %(z,))
        self._calculate_pseudo_mesh(positions)

    def _calculate_pseudo_mesh(self,positions):
        z_home = positions[2][2]
        for pos in positions:
            pos[0]=round(pos[0])
            pos[1]=round(pos[1])
            pos[2]=round((pos[2]-z_home),3)
        self.pseudo_mesh=positions
        self.gcode.respond_info("Pseudo Mesh generated: %s"
                                %(self.pseudo_mesh,))
        self.gcode.respond_info("Run BACK_TAP_MOVE POS=3 (1 to 5) to start calibrating")

    def _calibrate_move(self, pos):
        toolhead = self.printer.lookup_object('toolhead')
        if not self.pseudo_mesh:
            self.gcode.respond_info("Missing Mesh Data! Run BACK_TAP_CALIBRATE first.")
            return False
        x=self.pseudo_mesh[pos][0]
        y=self.pseudo_mesh[pos][1]
        z=self.pseudo_mesh[pos][2]
        self.gcode.respond_info("Moving to calibration point: %i at %s" %(pos+1,self.pseudo_mesh[pos],))
        #Move motions
        toolhead.manual_move([None, None, 15], self.calibration_lift_speed)
        toolhead.manual_move([x, y, None], self.calibration_speedself.speed)
        toolhead.manual_move([None, None, z], self.calibration_lift_speed/2)

        self.gcode.respond_info("Adjust Z-Offset and take note of the value, then move to another point ")

    def cmd_BACK_TAP_MOVE(self, gcmd):
        pos = (gcmd.get_int("POS", 3, minval=1, maxval=5))-1

        self._calibrate_move(pos)

    cmd_BACK_TAP_MOVE_help = "Move to points 1 and 5 and calculate the probe deviation offset using the paper test. Check 2 and 4 for "


def load_config(config):
    config.get_printer().add_object('probe', BackTapProbe(config, probe.ProbeEndstopWrapper(config)))
    return BackTapCalibration(config)

