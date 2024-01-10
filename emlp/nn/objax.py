import jax
import jax.numpy as jnp
import jax.scipy.stats as jss

import objax.nn as nn 
import numpy as np  
from scalaremlp.utils import Named,export 
from objax.module import Module 
from jax import jit,vmap 
from functools import partial
import itertools  

from typing import Callable, List

def Sequential(*args):
    """ Wrapped to mimic pytorch syntax"""
    return nn.Sequential(args)
 
def swish(x):
    return jax.nn.sigmoid(x)*x

@export
class BasicMLP_objax(Module):
    def __init__(
        self, 
        n_in: int, 
        n_out: int,
        n_hidden: int = 100, 
        n_layers: int = 2,
        div: int = 2 
    ):
        super().__init__()
        layers = [nn.Linear(n_in, n_hidden), swish]
        for _ in range(n_layers):
            layers.append(nn.Linear(n_hidden, n_hidden//div))
            layers.append(swish)
            n_hidden //= div 
        layers.append(nn.Linear(n_hidden, n_out))
        
        self.mlp = Sequential(*layers)
    
    def __call__(self,x,training=True):
        return self.mlp(x)

@export
class ScalarMLP(Module, metaclass=Named):
    """ Scalar Invariant MultiLayer Perceptron. 
    Arguments 
    -------
    n_in : int
        number of inputs to MLP
    n_hidden: int
        number of hidden units in MLP
    n_layers: int
        number of layers between input and output layers
    div: int
        scale the number of hidden units at each subsequent layer of MLP 
    transformer: Callable
        transformation attributes and functions
          
    Returns:
    -------
    Module: 
        the ScalarMLP objax module.
    """
    def __init__(
        self, 
        n_hidden: int, 
        n_layers: int, 
        div: int,
        transformer: Callable, 
    ): 
        super().__init__()  
         
        n_in = transformer.n_features
        self.transformer = transformer  

        self.mlp = BasicMLP_objax(
            n_in=n_in, n_out=1, n_hidden=n_hidden, n_layers=n_layers, div=div
        )   
    
    def H(self, x, xp):  
        scalars, _ = self.transformer(x,xp)  
        out = self.mlp(scalars)
        return out.sum()  
    
    def __call__(self, x, xp, training = True):
        return self.H(x, xp)
 
@export  
class InvarianceLayer_objax(ScalarMLP):
    def __init__(
        self, 
        n_hidden: int, 
        n_layers: int, 
        div: int,
        transformer: Callable, 
    ):   
        n_in = transformer.n_features
        n_out = transformer.n_scaling
        self.transformer = transformer  
        
        self.mlp = BasicMLP_objax(
            n_in=n_in, 
            n_out=n_out, 
            n_hidden=n_hidden, 
            n_layers=n_layers, 
            div=div
        )   
          
    
    def H(self, x, xp):  
        scalars, scaling = self.transformer(x,xp)  
        out = scaling * self.mlp(scalars)  
        return out.sum()  
    
    def __call__(self, x, xp, training = True):
        return self.H(x, xp)

@export
class Dimensionless(object):
    def __init__(self): 
        self.create_mapping()
        self.h = jnp.array(self.h)
        self.nh = jnp.array(self.nh) 
    
    def create_mapping(self):
        self.nh = np.zeros((26,21),dtype=np.float32)
        ## First group
        self.nh[0][2] = 1 # k1
        self.nh[0][4] = 2 # l1^2
        self.nh[1][3] = 1 # k2
        self.nh[1][5] = 2 # l2^2
        
        self.nh[2][3] = 1 # k2
        self.nh[2][4] = 2 # l1^2
        self.nh[3][2] = 1 # k1
        self.nh[3][5] = 2 # l2^2
        
        self.nh[4][2] = 1 # k1
        self.nh[4][4] = 1 # l1
        self.nh[4][5] = 1 # l2
        self.nh[5][3] = 1 # k2
        self.nh[5][4] = 1 # l1
        self.nh[5][5] = 1 # l2
        
        ## Second group
        self.nh[6][2] = 1 # k1 
        self.nh[6][18] = 2 # |q1|^2
        self.nh[7][3] = 1 # k2
        self.nh[7][20] = 2 # |q2-q1|^2
        self.nh[8][3] = 1 # k2 
        self.nh[8][18] = 2 # |q1|^2
        self.nh[9][2] = 1 # k1
        self.nh[9][20] = 2 # |q2-q1|^2
        self.nh[10][2] = 1 # k1 
        self.nh[10][18] = 1 # |q1|
        self.nh[10][20] = 1 # |q2-q1|
        self.nh[11][3] = 1 # k2
        self.nh[11][18] = 1 # |q1|
        self.nh[11][20] = 1 # |q2-q1|
        
        
        ## Third group
        self.nh[12][0] = -1 # 1/m1 
        self.nh[12][11] = 2 # |p1|^2
        self.nh[13][1] = -1 # 1/m2
        self.nh[13][15] = 2 # |p2|^2
        self.nh[14][1] = -1 # 1/m2 
        self.nh[14][11] = 2 # |p1|^2
        self.nh[15][0] = -1 # 1/m1
        self.nh[15][15] = 2 # |p2|^2
        self.nh[16][0] = -1 # 1/m1 
        self.nh[16][12] = 1 # p1Tp2
        self.nh[17][1] = -1 # 1/m2
        self.nh[17][12] = 1 # p1Tp2
        
        ## Fourth group
        self.nh[18][0] = 1 # m1 
        self.nh[18][9] = 1 # gTq1
        self.nh[19][1] = 1 # m2
        self.nh[19][10] = 1 # gT(q2-q1)
        self.nh[20][0] = 1 # m1 
        self.nh[20][10] = 1 # gT(q2-q1)
        self.nh[21][1] = 1 # m2
        self.nh[21][9] = 1 # gTq1
        
        ## Fifth group
        self.nh[22][0] = 1 # m1 
        self.nh[22][4] = 1 # l1
        self.nh[22][6] = 1 # |g|
        self.nh[23][1] = 1 # m2
        self.nh[23][5] = 1 # l2
        self.nh[23][6] = 1 # |g|
        self.nh[24][0] = 1 # m1 
        self.nh[24][5] = 1 # l2
        self.nh[24][6] = 1 # |g|
        self.nh[25][1] = 1 # m2
        self.nh[25][4] = 1 # l1
        self.nh[25][6] = 1 # |g|
        
        self.h = np.zeros((32,21),dtype=np.float32)
        # m1 / m2
        self.h[0][0] = 1 # m1
        self.h[0][1] = -1 # 1/m2
        # m2 / m1
        self.h[1][0] = -1 # 1/m1
        self.h[1][1] = 1 # m2
        # k1 / k2
        self.h[2][2] = 1 # k1
        self.h[2][3] = -1 # 1/k2
        # k2 / k1
        self.h[3][2] = -1 # 1/k1
        self.h[3][3] = 1 # k2
        # l1 / l2
        self.h[4][4] = 1 # l1
        self.h[4][5] = -1 # 1/l2
        # l2 / l1
        self.h[5][4] = -1 # 1/l1
        self.h[5][5] = 1 # l2
        
        # m1 |g| / k1 / l1
        self.h[6][0] = 1 # m1
        self.h[6][6] = 1 # |g|
        self.h[6][2] = -1 # 1/k1
        self.h[6][4] = -1 # 1/l1
        # m2 |g| / k2 / l2
        self.h[7][1] = 1 # m2
        self.h[7][6] = 1 # |g|
        self.h[7][3] = -1 # 1/k2
        self.h[7][5] = -1 # 1/l2
        
        # inv m1 |g| / k1 / l1
        self.h[8] = -self.h[6][:] 
        # inv m2 |g| / k2 / l2
        self.h[9] = -self.h[7][:]
        
        # gTp1 / (|g||p1|)
        self.h[10][7] = 1 # gTp1
        self.h[10][6] = -1 # 1/|g|
        self.h[10][11] = -1 # 1/|p1|
        # gTp2 / (|g||p2|)
        self.h[11][8] = 1 # gTp2
        self.h[11][6] = -1 # 1/|g|
        self.h[11][15] = -1 # 1/|p2|
        # gTq1 / (|g||q1|)
        self.h[12][9] = 1 # gTq1 
        self.h[12][6] = -1 # 1/|g|
        self.h[12][18] = -1 # 1/|q1|
        # gTq2 / (|g||q2-q1|)
        self.h[13][10] = 1 # gT(q2-q1) 
        self.h[13][6] = -1 # 1/|g|
        self.h[13][20] = -1 # 1/|q2-q1|
        
        # p1Tp2 / (|p1||p2|)
        self.h[14][12] = 1 # p1Tp2
        self.h[14][11] = -1 # 1/|p1|
        self.h[14][15] = -1 # 1/|p2|
        # p1Tq1 / (|p1||q1|)
        self.h[15][13] = 1 # p1Tq1
        self.h[15][11] = -1 # 1/|p1|
        self.h[15][18] = -1 # 1/|q1|
        # p1T(q2-q1) / (|p1||q2-q1|)
        self.h[16][14] = 1 # p1T(q2-q1)
        self.h[16][11] = -1 # 1/|p1|
        self.h[16][20] = -1 # 1/|q2-q1|
        # p2Tq1 / (|p2||q1|)
        self.h[17][16] = 1 # p2Tq1 
        self.h[17][15] = -1 # 1/|p2|
        self.h[17][18] = -1 # 1/|q1|
        # p2T(q2-q1) / (|p2||q2-q1|)
        self.h[18][17] = 1 # p2T(q2-q1) 
        self.h[18][15] = -1 # 1/|p2|
        self.h[18][20] = -1 # 1/|q2-q1|
        # q1T(q2-q1) / (|q1||q2-q1|)
        self.h[19][19] = 1 # q1T(q2-q1)
        self.h[19][18] = -1 # 1/|q1|
        self.h[19][20] = -1 # 1/|q2-q1|
        
        # |q1|/l1
        self.h[20][18] = 1 # |q1|
        self.h[20][4] = -1 # 1/l1
        # |q2-q1|/l2
        self.h[21][20] = 1 # |q2-q1|
        self.h[21][5] = -1 # 1/l2
        
        # |p1|/(l1 sqrt(m1k1))
        self.h[22][11] = 1 # |p1|
        self.h[22][4] = -1 # 1/|l1|
        self.h[22][0] = -1/2 # 1/sqrt(m1)
        self.h[22][2] = -1/2 # 1/sqrt(k1)
        # |p2|/(l2 sqrt(m2k2))
        self.h[23][15] = 1 # |p2|
        self.h[23][5] = -1 # 1/|l2|
        self.h[23][1] = -1/2 # 1/sqrt(m2)
        self.h[23][3] = -1/2 # 1/sqrt(k2)
        
        self.h[24] = self.h[6] * 2
        self.h[25] = self.h[7] * 2
        self.h[26] = self.h[8] * 2
        self.h[27] = self.h[9] * 2
        
        self.h[28] = self.h[20] * 2
        self.h[29] = self.h[21] * 2
        self.h[30] = self.h[22] * 2
        self.h[31] = self.h[23] * 2
         
     

    def map_m_func(self, params, x):
        """x (d,) and h (m,d) gives output (m,)"""
        return jnp.prod(x**params, axis=-1)

    # def map_s_func(self, params, x):
    #     """x (d,) and h (2,d) gives output (1,)"""
    #     return jnp.sum(jnp.prod(x**params, axis=-1), keepdims=True)

    def __call__(self, x):
        """
        Input 
        - x: scalars with dimensions (n, d)
        Output
        - x_dl: dimensionless scalars (n, m)
        - x_sc: scaling (n,2)  
        """
        ## Broadcasting: (n, d) & (m, d) => (n, m, d) => (n, m)
        x_dl = jit(vmap(jit(partial(self.map_m_func, self.h))))(x)
        
        ## Broadcasting: (n, d) & (2, d) => (n, 2, d) => (n, 2)
        x_sc = jit(vmap(jit(partial(self.map_m_func, self.nh))))(x) 
        return x_dl, x_sc 

@export
class ScalarTransformer(object):
    """Transform (dimensionless) features using quantiles info or radial basis function.
    
    During the initialization stage, this method takes the whole training data set, 
    zs (n,4,3) and zps (n,9), and conducts the following transformation: 
                zs, zps
        Step 0  => inner product scalars 
        Step 1  => dimensionless scalars                   (optional, dimensionless = True)
        Step 2  => rbf (or quantile) transformed scalars   (optional, method = 'rbf' (method = 'qt'))
    Either one or both of the two optional steps can be skipped. 
    If method is not 'none', transformer information (parameters) is recorded.
    
    When the Object is called, the input scalars go through: 
        Step 1 (optional)
        Step 2 (optional)
    depending on the values of the arguments, dimensionless and method
            
    
    Arguments
    ----------
    zs : jax.numpy.ndarray (n, 4, 3)
        Double pendulum TRAINING data positions and velocities q1, q2, p1, p2

    zps : jax.numpy.ndarray (n, 9) 
        Double pendulum TRAINING data parameters g, m1, m2, k1, k2, l1, l2
    
    dimensionless : bool
        whether we want to make the scalars dimensionless 
    
    method : str, 'qt' or 'rbf' or 'none'

    n_quantiles : int, default=1000 or n
        Number of quantiles to be computed. It corresponds to the number
        of landmarks used to discretize the cumulative distribution function.


    Attributes
    ----------
    n_features : int 
        number of features in the (dimensionless) (transformed) output

    dimensionless_operator : lambda x : (x,1) or emlp.nn.objax.Dimensionless() funcion
        

    ===========================================================================
    rbf : Transform features using radial basis function

    qt: Transform features using quantiles information  
        Adapted from scikit_learn.preprocessing.QuantileTransformer. 

        This method transforms the features to follow a uniform or a normal
        distribution. Therefore, for a given feature, this transformation tends
        to spread out the most frequent values. It also reduces the impact of
        (marginal) outliers: this is therefore a robust preprocessing scheme.
        
        The transformation is applied on each feature independently. 
        
        Features values of new/unseen data that fall below or above the fitted range 
        will be mapped to the bounds of the output distribution. 
        
        Note that this transform is non-linear. It may distort linear
        correlations between variables measured at the same scale but renders
        variables measured at different scales more directly comparable. 

    none : Only perform standardization for each feature 
    """
    def __init__(
        self, 
        zs, 
        zps, 
        method: str = 'none', 
        dimensionless: bool = False,
        n_rad: int = 100,
        n_quantiles: int = 1000, 
        transform_distribution: str = 'uniform'   
    ):  
        zs, zps = jnp.array(zs), jnp.array(zps)
        # Create mapping idex for inner product scalars computation
        self._create_index()
        
        self.dimensionless = dimensionless
        # Create inner product scalars
        scalars = self._compute_scalars(
            zs, 
            zps[:,:3], 
            zps[:,3:]
        )   
        print(f"Scalars min={jnp.round(jnp.min(jnp.abs(scalars), axis=0), 4)}")
        print(f"Scalars max={jnp.round(jnp.max(jnp.abs(scalars), axis=0), 4)}")
        
        self.n_scaling = 26
        self.dimensionless_operator = lambda x: (x, jnp.ones((self.n_scaling,))) 
        self.scaling_standardization = jnp.vstack([jnp.zeros((self.n_scaling,)),jnp.ones((self.n_scaling,))])
        
        if self.dimensionless:
            # Create dimensionless features 
            self.dimensionless_operator = Dimensionless() 
            scalars, scaling = self.dimensionless_operator(scalars)
            print(f"Dimensionless scalars min={jnp.round(jnp.min(jnp.abs(scalars), axis=0), 4)}")
            print(f"Dimensionless scalars max={jnp.round(jnp.max(jnp.abs(scalars), axis=0), 4)}")
            print(f"Dimensionless scaling max={jnp.round(jnp.max(scaling, axis=0), 2)} and min={jnp.round(jnp.min(scaling, axis=0), 4)}")
            self.scaling_standardization = jnp.vstack(
                [jnp.min(scaling, axis=0), jnp.max(scaling, axis=0) - jnp.min(scaling, axis=0)] 
            )
            self.n_scaling = scaling.shape[-1]
        # print(f"Dimension of features is {scalars.shape[1]}, and the rank is {jnp.linalg.matrix_rank(scalars)}")
        

        self.method = method
        self.n_rad = n_rad
        self.n_quantiles = n_quantiles
        self.transform_distribution = transform_distribution
        # Create the quantiles of reference
        self.references = jnp.linspace(0, 1, self.n_quantiles, endpoint=True)
        self.BOUNDS_THRESHOLD = 1e-7 
        self.spacing = jnp.array(np.spacing(1)) 
        
        self._GETPARAMS = {
            'qt': self._get_qt_params,
            'rbf': self._get_rbf_params, 
            'none': self._get_none_params
        }
        
        # Compute the global quansformation parameters
        self._GETPARAMS[self.method](scalars)
       
        self._TRANSFORMS = {
            'qt': self._qt_transform,
            'rbf': self._rbf_transform,
            'none': self._none_transform
        }

    def _create_index(self):
        """create the indexing for the construction of the inner product scalars"""
        idx = jnp.array(
            list(itertools.combinations_with_replacement(jnp.arange(0,4), r=2))
        )
        self.idx_map = jnp.array([2,3,0,1])
        self.idx = self.idx_map[idx] 
        self.idx_sqrt = jnp.concatenate(
            [jnp.zeros(1, dtype=int), jnp.cumsum(jnp.arange(2,5)[::-1])], 
            axis=0
        ) 

    def _get_none_params(self, x):
        """Gets parameters for standardization transformation:
        
        Arguments 
        -----------
        x : jax.numpy.ndarray (n, d)

        Returns
        -----------
        params : jax.numpy.ndarray (2, d)
            params[0] gives mean
            params[1] gives std

        n_features: int 
            number of features in the transformed output

        """ 
        # If transformer method == "none":
        self.parameters = jnp.stack([jnp.mean(x, axis = 0), jnp.std(x, axis = 0)], axis = 0)
        self.n_features = x.shape[-1]

    def _get_rbf_params(self, x):
        """Gets parameters for Radial Basis Function Transformation:
        
        Arguments 
        -----------
        x : jax.numpy.ndarray (n, d)

        n_rad : int
            number of transformed outputs for each d

        Returns
        -----------
        params : jax.numpy.ndarray (n_rad+1, d)
            params[0] gives gamma (1, d)
            params[1:] gives mu (n_rad, d)

        n_features: int 
            number of features in the transformed output

        Remarks
        -----------
        Given mu (n,d) and gamma (d,), RBF for x (n,d) gives x_trans (n,n_rad)
        x_trans[:,i] = exp(-gamma[:,i]*(x[:,i]-mu[:,i])**2), i=1,...,d

        """ 
        xmin = jnp.min(x, axis=0, keepdims=True) # (1,d) 
        xmax = jnp.max(x, axis=0, keepdims=True) # (1,d)
        gamma = 2*(xmax - xmin)/(self.n_rad - 1) # (1,d)
        mu    = jnp.linspace(start=xmin[0], stop=xmax[0], num=self.n_rad) # (nrad, d)
        self.parameters = jnp.concatenate([gamma, mu], axis=0) # (n_rad+1,d)
        self.n_features = x.shape[1]*self.n_rad
        
    def _get_qt_params(self, x): 
        """Gets parameters for Quantile Transformation
        
        Arguments:
        ----------
        x : jax.numpy.ndarray (n, d)

        self.references : (array_like of float) 
            Percentile or sequence of percentiles to compute, 
            which must be between 0 and 100 inclusive.

        Returns 
        ---------
        quantiles : numpy.ndarray of shape (n_quantiles, d)
            The values corresponding the quantiles of reference.

        n_features: int 
            number of features in the transformed output
        """ 
        self.parameters = jnp.nanpercentile(x, self.references*100, axis=0)
        self.n_features = x.shape[1] 
    
    def _none_transform(self, X):
        return (X-self.parameters[0])/self.parameters[1]

    def _rbf_transform(self, X):
        """RBF : Transform features using radial basis function 

        Arguments
        ----------
        X : jax.numpy.ndarray (n, d)

        self.parameters : jax numpy ndarray (n_rad+1, d)
            self.parameters[0] gives gamma (1, d)
            self.parameters[1:] gives mu (n_rad, d)

        Returns
        ----------
        X : jax.numpy.ndarray (n, n_rad*d)
        """
        n = X.shape[0]
        return jnp.exp(-self.parameters[0] * (X-self.parameters[1:])**2).reshape(n,-1)
    
    def _qt_transform(self, X): 
        """Forward quantile transform.
        
        Arguments
        ----------
        X : jax.numpy.ndarray of shape (n, d)
            The data used to scale along the features axis. 

        self.parameters : jax.numpy.ndarray of shape (n_quantiles, d)
            The values corresponding the quantiles of reference.
        
        self.transform_distribution : {'uniform', 'normal'}, default='uniform'
            Marginal distribution for the transformed data. The choices are
            'uniform' (default) or 'normal'.

        Returns
        -------
        X : jax ndarray of shape (n, d)
            Projected data.
        """ 
        
        X = vmap(jit(self._qt_transform_col), in_axes=(1,1), out_axes=1)(X, self.parameters) 
        return X

    def _qt_transform_col(self, X_col, params):
        """Private function to forward transform a single feature."""
        lower_bound_x = params[0]
        upper_bound_x = params[-1]
        lower_bound_y = 0
        upper_bound_y = 1
        n = X_col.shape[0]

        lower_bounds_idx = jnp.nonzero(
            X_col - self.BOUNDS_THRESHOLD < lower_bound_x, 
            size = n, 
            fill_value = n+1
        )
         
        upper_bounds_idx = jnp.nonzero(
            X_col + self.BOUNDS_THRESHOLD > upper_bound_x, 
            size = n, 
            fill_value = n+1
        )
        
        # Interpolate in one direction and in the other and take the
        # mean. This is in case of repeated values in the features
        # and hence repeated quantiles
        #
        # If we don't do this, only one extreme of the duplicated is
        # used (the upper when we do ascending, and the
        # lower for descending). We take the mean of these two
          
        X_col = 0.5 * (
            jnp.interp(X_col, params, self.references)
            - jnp.interp(-X_col, -params[::-1], -self.references[::-1])
        )
         
        X_col = X_col.at[upper_bounds_idx].set(upper_bound_y)
        X_col = X_col.at[lower_bounds_idx].set(lower_bound_y)

        # for forward transform, match the output PDF
        if self.transform_distribution == "normal":  
            X_col = jss.norm.ppf(X_col)
            # find the value to clip the data to avoid mapping to
            # infinity. Clip such that the inverse transform will be
            # consistent
            clip_min = jss.norm.ppf(self.BOUNDS_THRESHOLD - self.spacing)
            clip_max = jss.norm.ppf(1 - (self.BOUNDS_THRESHOLD - self.spacing))
            X_col = jnp.clip(X_col, clip_min, clip_max)
        
        # else output distribution is uniform and the ppf is the
        # identity function so we let X_col unchanged
        return X_col
    
    def _compute_scalars(self, x, g, mkl):
        """Input x of dim (n,4,3), g of dim (n,3), mkl = (m1, m2, k1, k2, l1, l2) of (n,6)"""
        # get q2 - q1 replacing q2
        x = x.at[:,1,:].set(x[:,1,:]-x[:,0,:])  
        xx = jnp.sum(
            x[:,self.idx[:,0],:] * x[:,self.idx[:,1],:], 
            axis=-1
        ) # (n, 10)
        gx = jnp.einsum("...j,...ij", g, x[:,self.idx_map]) # (n, 4)
        gg = jnp.sum(g*g, axis = -1, keepdims=True) # (n, 1)
        if self.dimensionless:
            xx = xx.at[:,self.idx_sqrt].set(jnp.sqrt(xx[:,self.idx_sqrt])) 
            ## all the current scalars we have 
            scalars = jnp.concatenate([mkl, jnp.sqrt(gg), gx, xx], axis = -1) # (n, 21)
        else:
            xxsqrt = jnp.sqrt(xx[:,self.idx_sqrt]) # (n, 4)
            ggsqrt = jnp.sqrt(gg) # (n, 1)
            scalars = jnp.concatenate([mkl, gg, gx, xx, ggsqrt, xxsqrt, 1/mkl], axis=-1) # (n, 32)
        return scalars  

    def __call__(self, xs, xps):
        g, mkl = xps[...,:3], xps[...,3:] # (n,3), (n,6)  
        # Compute inner product scalars 
        scalars = self._compute_scalars(
            xs.reshape(-1,4,3), g.reshape(-1,3), mkl.reshape(-1,6)
        )
        # Create dimensionless features 
        scalars, scaling = self.dimensionless_operator(scalars)
        
        # Standardize scalings 
        scaling = (scaling - self.scaling_standardization[0]) / self.scaling_standardization[1]
        
        return jit(self._TRANSFORMS[self.method])(scalars), scaling

    
    
