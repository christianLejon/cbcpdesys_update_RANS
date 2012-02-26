__author__ = "Mikael Mortensen <mikaem@math.uio.no>"
__date__ = "2010-08-30"
__copyright__ = "Copyright (C) 2010 " + __author__
__license__  = "GNU GPL version 3 or any later version"

"""
Turbulent flow in an axial diffusor
"""
# import the diffusor mesh and parameters from the laminar problem case
from cbc.cfd.problems.diffusor import *
from cbc.cfd import icns                    # Navier-Stokes solvers
from cbc.cfd import ransmodels              # RANS models
from cbc.cfd.icns import solver_parameters  # parameters for NS
from cbc.cfd.ransmodels import solver_parameters as rans_parameters # parameters for RANS model
set_log_active(True)

import cPickle
from numpy import sign as numpy_sign

class channel_flow(Expression):
    """Initialize sub_systems in the PDESystems hierarchy with solution
    from a fully developed plane channel flow.
    The sub_system can be any composition of different function spaces,
    e.g., ['u', 'p'], ['k', 'e'], ['k', 'R'] where u is a vector, R is a
    second rank tensor and the rest are scalars. Initializes using dictionary
    q0 that must be using InterpolatedUnivariateSplines created for example by
    channel.tospline().
    The value_shape of this Expression depends on the sub_system and cannot
    be hardcoded. It can be computed as 
       value_shape = 0
       for key in self.sub_system:
           value_shape += len(self.q0[key])
    """
    
    def __init__(self, sub_system, q0=None, dy=None, **kwargs):
        self.sub_system = sub_system
        self.q0 = q0
        self.dy = dy
    
    def eval(self, values, x):
        y0 = self.dy(x[0]) # Bump height at x[0]
        y = abs(1. - (x[1] + y0)/(2.*y0)*2.)
        i = 0
        for key in self.sub_system:
            if key == 'Fij' or key == 'Rij': # requires treatment for anti-symmetry
                for q in self.q0[key]:
                    if i == 1 or i == 2 or i == 5 or i == 6:
                        values[i] = -numpy_sign(1. - (x[1] + y0)/(2.*y0)*2.)*q(y)
                    else:
                        values[i] = q(y)
                    i += 1                
            else:
                for q in self.q0[key]:
                    values[i] = q(y)
                    i += 1
                    
# Subclass diffusor to allow a quite complicating initialization routine that
# actually works for any pdesystem as long as there is a dictionary of splines
# in ../data/channel_...
NSdiffusor = diffusor
class diffusor(NSdiffusor):
    def initialize(self, pdesystem):
        """
        This routine is called in the creation of a pdesystem. 
        Load a spline computed from a turbulent channel problem.
        Use this spline to initialize the solution throughout the diffusor.
        q0 is also used to set the DirichletBC's on the VelocityInlet.
        """
        f = open('../../data/channel_' + self.prm['turbulence_model'] + '_' + 
                 str(self.prm['Re_tau']) + '.ius','r')
        inspline = cPickle.load(f)
        f.close()
        
        for sub_system in pdesystem.system_composition:
            name = ''.join(sub_system)            
            self.q0[name] = channel_flow(sub_system, q0=inspline, dy=self.dy,
                                         element=pdesystem.V[name].ufl_element())
            
            # VelocityInlet requires an instance of self.q0['u'], because DirichletBC is only on 'u' and not 'p'. So for coupled solve this must be added
            if name == 'up':
                self.q0['u'] = channel_flow(['u'], q0=inspline, dy=self.dy, 
                                            element=pdesystem.V['u'].ufl_element())
                                  
        # Perform initialization
        return NSdiffusor.initialize(self, pdesystem)

if __name__=='__main__':
    # Set up turbulent diffusor problem
    problem_parameters['time_integration']='Steady'
    problem_parameters['Re_tau'] = Re_tau= 395.
    problem_parameters['utau'] = utau = 0.05
    problem_parameters['plot_velocity'] = True
    problem_parameters['pressure_bc'] = False
    problem_parameters['Nx'] = 10
    problem_parameters['Ny'] = 100
    problem = diffusor(problem_parameters)
    problem.prm['viscosity'] = utau/Re_tau
    problem_parameters['turbulence_model'] = 'OriginalV2F'
    
    ## Set up Navier-Stokes solver ##
    solver_parameters['degree']['u'] = 1
    solver_parameters['omega'].default_factory = lambda : 0.8
    NS_solver = icns.NSCoupled(problem, solver_parameters)
    
    ## Set up turbulence model ##
    rans_parameters['omega'].default_factory = lambda : 0.6
    Turb_solver = ransmodels.V2F_2Coupled(problem, rans_parameters,
                                 model=problem_parameters['turbulence_model'])
    
    ## solve the problem ##    
    t0 = time()
    problem_parameters['max_iter'] = 10
    problem.solve()
    print 'time = ', time()-t0
    print summary()
    plot(NS_solver.u_)
    #interactive()

