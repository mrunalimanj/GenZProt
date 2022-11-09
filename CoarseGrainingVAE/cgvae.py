
import torch
from torch import nn
from .conv import * 
from torch_scatter import scatter_mean, scatter_add

class ENDecoder(nn.Module):
    def __init__(self, n_atom_basis, n_rbf, cutoff, num_conv, activation ):   
        
        nn.Module.__init__(self)
        # distance transform
        self.dist_embed = DistanceEmbed(n_rbf=n_rbf,
                                  cutoff=cutoff,
                                  feat_dim=n_atom_basis,
                                  dropout=0.0)

        self.message_blocks = nn.ModuleList(
            [ENMessageBlock(feat_dim=n_atom_basis,
                          activation=activation,
                          n_rbf=n_rbf,
                          cutoff=cutoff,
                          dropout=0.0)
             for _ in range(num_conv)]
        )

    
    def forward(self, cg_xyz, CG_nbr_list, cg_s):
    
        CG_nbr_list, _ = make_directed(CG_nbr_list)
        r_ij = cg_xyz[CG_nbr_list[:, 1]] - cg_xyz[CG_nbr_list[:, 0]]
        
        v_i = torch.zeros(cg_s.shape[0], cg_s.shape[1], 3 ).to(cg_s.device)
        s_i = cg_s

        # inputs need to come from atomwise feature toulene_dft
        for i, message_block in enumerate(self.message_blocks):
            
            # message block
            ds_message, dv_message = message_block(s_j=s_i,
                                                   v_j=v_i,
                                                   r_ij=r_ij,
                                                   nbrs=CG_nbr_list,
                                                   )
            s_i = s_i + ds_message
            v_i = v_i + dv_message
            
        return s_i, v_i 



class EquivariantPsuedoDecoder(nn.Module):
    def __init__(self, n_atom_basis, n_rbf, cutoff, num_conv, activation, breaksym=False):   
        
        nn.Module.__init__(self)
        
        self.message_blocks = nn.ModuleList(
                [EquiMessagePsuedo(feat_dim=n_atom_basis,
                              activation=activation,
                              n_rbf=n_rbf,
                              cutoff=cutoff,
                              dropout=0.0)
                 for _ in range(num_conv)]
            )

        self.update_blocks = nn.ModuleList(
            [UpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(num_conv)]
        )


        self.pseudo_update_blocks = nn.ModuleList(
            [PseudoUpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(num_conv)]
        )

        self.breaksym = breaksym
        self.n_atom_basis = n_atom_basis

    
    def forward(self, cg_xyz, CG_nbr_list, mapping, S):
    
        CG_nbr_list, _ = make_directed(CG_nbr_list)
        r_ij = cg_xyz[CG_nbr_list[:, 1]] - cg_xyz[CG_nbr_list[:, 0]]

        V = torch.zeros(S.shape[0], S.shape[1], 3 ).to(S.device)
        if self.breaksym:
            Sbar = torch.ones(S.shape[0], S.shape[1]).to(S.device)
        else:
            Sbar = torch.zeros(S.shape[0], S.shape[1]).to(S.device)
        Vbar = torch.zeros(S.shape[0], S.shape[1], 3 ).to(S.device)

        for i, message_block in enumerate(self.message_blocks):
            
            # message block
            dS, dSbar, dV, dVbar = message_block(s_j=S,
                                                   sbar_j = Sbar,
                                                   v_j=V,
                                                   vbar_j=Vbar,
                                                   r_ij=r_ij,
                                                   nbrs=CG_nbr_list,
                                                   edge_wgt=None
                                                   )
            S = S + dS
            Sbar = Sbar + dSbar
            V = V + dV
            Vbar = Vbar + dVbar 

            # update block
            dS_update, dV_update = self.update_blocks[i](s_i=S,
                                                v_i=V)
            # dSbar_update, dVbar_update = self.pseudo_update_blocks[i](s_i=Sbar,
            #                                     v_i=Vbar)

            # Sbar = Sbar + dSbar_update
            # Vbar = Vbar + dVbar_update

            S = S + dS_update
            V = V + dV_update

        return S, V 


class internalEquivariantPsuedoDecoder(nn.Module):
    def __init__(self, n_atom_basis, n_rbf, cutoff, num_conv, activation, breaksym=False):   
        
        nn.Module.__init__(self)
        
        self.message_blocks = nn.ModuleList(
                [EquiMessagePsuedo(feat_dim=n_atom_basis,
                              activation=activation,
                              n_rbf=n_rbf,
                              cutoff=cutoff,
                              dropout=0.0)
                 for _ in range(num_conv)]
            )

        self.update_blocks = nn.ModuleList(
            [UpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(num_conv)]
        )


        self.pseudo_update_blocks = nn.ModuleList(
            [PseudoUpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(num_conv)]
        )

        # self.linear = nn.Linear(n_atom_basis, 3)

        self.breaksym = breaksym
        self.n_atom_basis = n_atom_basis

    
    def forward(self, cg_xyz, CG_nbr_list, mapping, S):
    
        CG_nbr_list, _ = make_directed(CG_nbr_list)
        r_ij = cg_xyz[CG_nbr_list[:, 1]] - cg_xyz[CG_nbr_list[:, 0]]

        V = torch.zeros(S.shape[0], S.shape[1], 3 ).to(S.device)
        if self.breaksym:
            Sbar = torch.ones(S.shape[0], S.shape[1]).to(S.device)
        else:
            Sbar = torch.zeros(S.shape[0], S.shape[1]).to(S.device)
        Vbar = torch.zeros(S.shape[0], S.shape[1], 3 ).to(S.device)

        for i, message_block in enumerate(self.message_blocks):
            
            # message block
            dS, dSbar, dV, dVbar = message_block(s_j=S,
                                                   sbar_j = Sbar,
                                                   v_j=V,
                                                   vbar_j=Vbar,
                                                   r_ij=r_ij,
                                                   nbrs=CG_nbr_list,
                                                   edge_wgt=None
                                                   )
            S = S + dS
            Sbar = Sbar + dSbar
            V = V + dV
            Vbar = Vbar + dVbar 

            # update block
            dS_update, dV_update = self.update_blocks[i](s_i=S,
                                                v_i=V)
            # dSbar_update, dVbar_update = self.pseudo_update_blocks[i](s_i=Sbar,
            #                                     v_i=Vbar)

            # Sbar = Sbar + dSbar_update
            # Vbar = Vbar + dVbar_update

            S = S + dS_update
            V = V + dV_update

        return S, V 


class MLPDecoder(nn.Module):
    def __init__(self, n_atom_basis, n_rbf, cutoff, num_conv, activation, cross_flag=True):   
        nn.Module.__init__(self)

        self.inv_message = InvariantMessage(in_feat_dim=n_atom_basis,
                                    out_feat_dim=n_atom_basis, 
                                    activation=activation,
                                    n_rbf=n_rbf,
                                    cutoff=cutoff,
                                    dropout=0.0)

        self.inv_message2 = InvariantMessage(in_feat_dim=n_atom_basis,
                                    out_feat_dim=n_atom_basis, 
                                    activation=activation,
                                    n_rbf=n_rbf,
                                    cutoff=cutoff,
                                    dropout=0.0)

        # self.local_dense = nn.Sequential(nn.ReLU(), 
        #                            nn.Linear(n_atom_basis, 26), 
        #                            nn.ReLU(), 
        #                            nn.Linear(26, 26))
        
        # self.dih_dense = nn.Sequential(nn.ReLU(), 
        #                            nn.Linear(n_atom_basis+26, 13), 
        #                            nn.ReLU(), 
        #                            nn.Linear(13, 13))
        self.dense1 = nn.Sequential(nn.ReLU(), 
                                   nn.Linear(n_atom_basis, n_atom_basis), 
                                   nn.ReLU(), 
                                   nn.Linear(n_atom_basis, n_atom_basis))
        
        self.dense2 = nn.Sequential(nn.ReLU(), 
                                   nn.Linear(n_atom_basis, n_atom_basis), 
                                   nn.ReLU(), 
                                   nn.Linear(n_atom_basis, n_atom_basis))

        self.dense3 = nn.Sequential(nn.ReLU(), 
                                   nn.Linear(n_atom_basis, 39), 
                                   nn.ReLU(), 
                                   nn.Linear(39, 39))

    def forward(self, cg_xyz, CG_nbr_list, mapping, S, mask=None):   
        CG_nbr_list, _ = make_directed(CG_nbr_list)

        r_ij = cg_xyz[CG_nbr_list[:, 1]] - cg_xyz[CG_nbr_list[:, 0]]

        # S = torch.zeros_like(S).to(S.device)
        dist, unit = preprocess_r(r_ij)
        inv_out = self.inv_message(s_j=S,
                                   dist=dist,
                                   nbrs=CG_nbr_list)
        graph_size = S.shape[0]

        v_i = scatter_add(src=inv_out,
                    index=CG_nbr_list[:, 0],
                    dim=0,
                    dim_size=graph_size)

        v_i = S + self.dense1(v_i)

        inv_out = self.inv_message2(s_j=v_i,
                                   dist=dist,
                                   nbrs=CG_nbr_list)
        
        v_i_2 = scatter_add(src=inv_out,
                    index=CG_nbr_list[:, 0],
                    dim=0,
                    dim_size=graph_size)

        v_i = v_i + self.dense2(v_i_2)
        
        V = self.dense3(v_i) 
        V = V.reshape(-1,13,3)
        # print(V[0])
        return None, V


class SequentialDecoder(nn.Module):
    def __init__(self, n_atom_basis, n_rbf, cutoff, num_conv, activation, cross_flag=True):   
        nn.Module.__init__(self)

        # === networks for CG message passing
        self.inv_message = InvariantMessage(in_feat_dim=n_atom_basis,
                                    out_feat_dim=n_atom_basis, 
                                    activation=activation,
                                    n_rbf=n_rbf,
                                    cutoff=cutoff,
                                    dropout=0.0)

        self.inv_message2 = InvariantMessage(in_feat_dim=n_atom_basis,
                                    out_feat_dim=n_atom_basis, 
                                    activation=activation,
                                    n_rbf=n_rbf,
                                    cutoff=cutoff,
                                    dropout=0.0)

        self.dense1 = nn.Sequential(to_module(activation), 
                                   nn.Linear(n_atom_basis, n_atom_basis), 
                                   to_module(activation), 
                                   nn.Linear(n_atom_basis, n_atom_basis))
        
        self.dense2 = nn.Sequential(to_module(activation), 
                                   nn.Linear(n_atom_basis, n_atom_basis), 
                                   to_module(activation), 
                                   nn.Linear(n_atom_basis, int(n_atom_basis/2)))
        self.dense3 = nn.Linear(n_atom_basis, int(n_atom_basis/2))
        # === networks for backbone generation
        self.backbone_net = nn.ModuleList([nn.Sequential(to_module(activation), 
                                   nn.Linear(int(n_atom_basis/2), int(n_atom_basis/2)), 
                                   to_module(activation), 
                                   nn.Linear(int(n_atom_basis/2), int(n_atom_basis/2))) for _ in range(3)])

        # === networks for sidechain generation

        self.sidechain_net = nn.ModuleList([
                            nn.Sequential(to_module(activation), 
                                   nn.Linear(n_atom_basis*2, n_atom_basis), 
                                   to_module(activation), 
                                   nn.Linear(n_atom_basis, int(n_atom_basis/2)))
                            for _ in range(10)
                                    ])
        
        self.v_to_ic = nn.Sequential(to_module(activation), 
                                   nn.Linear(int(n_atom_basis/2), int(n_atom_basis/2)), 
                                   to_module(activation), 
                                   nn.Linear(int(n_atom_basis/2), 3))

    def forward(self, cg_xyz, CG_nbr_list, mapping, S, mask=None):   
        
        # ==== get CG feature by message passing 
        CG_nbr_list, _ = make_directed(CG_nbr_list)

        r_ij = cg_xyz[CG_nbr_list[:, 1]] - cg_xyz[CG_nbr_list[:, 0]]

        dist, unit = preprocess_r(r_ij)
        inv_out = self.inv_message(s_j=S,
                                   dist=dist,
                                   nbrs=CG_nbr_list)
        graph_size = S.shape[0]

        v_add = scatter_add(src=inv_out,
                    index=CG_nbr_list[:, 0],
                    dim=0,
                    dim_size=graph_size)

        v_cg = S + self.dense1(v_add)

        inv_out = self.inv_message2(s_j=v_cg,
                                   dist=dist,
                                   nbrs=CG_nbr_list)
        
        v_add = scatter_add(src=inv_out,
                    index=CG_nbr_list[:, 0],
                    dim=0,
                    dim_size=graph_size)

        v_cg = self.dense3(v_cg) + self.dense2(v_add) 
        # ==== generate backbone structure
        v_list = [bb_net(v_cg) for bb_net in self.backbone_net]
        # ==== generate sidechain structure
        for i in range(10):
            v_info = torch.cat([v_cg] + v_list[i:i+3], axis=-1)
            v_i = self.sidechain_net[i](v_info)
            v_list.append(v_i)
        v_list = torch.stack(v_list, axis=1).reshape(-1, 16)
        ic_list = self.v_to_ic(v_list)
        ic_list = ic_list.reshape(-1,13,3)
        print(ic_list[0])
        return None, ic_list

class EquivariantDecoder(nn.Module):
    def __init__(self, n_atom_basis, n_rbf, cutoff, num_conv, activation, cross_flag=True):   
        
        nn.Module.__init__(self)

        if cross_flag:
            self.message_blocks = nn.ModuleList(
                [EquiMessageCross(feat_dim=n_atom_basis,
                              activation=activation,
                              n_rbf=n_rbf,
                              cutoff=cutoff,
                              dropout=0.0)
                 for _ in range(num_conv)]
            )
        else: 
            self.message_blocks = nn.ModuleList(
                [EquiMessageBlock(feat_dim=n_atom_basis,
                              activation=activation,
                              n_rbf=n_rbf,
                              cutoff=cutoff,
                              dropout=0.0)
                 for _ in range(num_conv)]
            )

        self.update_blocks = nn.ModuleList(
            [UpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(num_conv)]
        )

        self.n_atom_basis = n_atom_basis

        # sj edit
        self.dense = nn.Sequential(nn.ReLU(), 
                                   nn.Linear(n_atom_basis, 39), 
                                   nn.ReLU(), 
                                   nn.Linear(39, 39))
    
    def forward(self, cg_xyz, CG_nbr_list, mapping, H, mask=None):
    
        CG_nbr_list, _ = make_directed(CG_nbr_list)
        r_ij = cg_xyz[CG_nbr_list[:, 1]] - cg_xyz[CG_nbr_list[:, 0]]

        V = torch.zeros(H.shape[0], H.shape[1], 3 ).to(H.device)

        # compute node degree 
        deg_inv_sqrt = scatter_add(torch.ones(CG_nbr_list.shape[0]).to(H.device), index=CG_nbr_list[:,0]).reciprocal().sqrt()

        for i, message_block in enumerate(self.message_blocks):
            
            # message block
            dH_message, dV_message = message_block(s_j=H,
                                                   v_j=V,
                                                   r_ij=r_ij,
                                                   nbrs=CG_nbr_list,
                                                   edge_wgt=None#deg_inv_sqrt[CG_nbr_list[:,0]] * deg_inv_sqrt[CG_nbr_list[:,1]]
                                                   )
            H = H + dH_message
            V = V + dV_message

            # update block
            dH_update, dV_update = self.update_blocks[i](s_i=H,
                                                v_i=V)
            H = H + dH_update
            V = V + dV_update

        # sj edit
        V = V.sum(axis=-1)
        V = V.reshape(-1,78)
        V = self.dense(V)
        V = V.reshape(-1,13,3)
        return H, V 


class EquiEncoder(nn.Module):
    
    def __init__(self,
             n_conv,
             n_atom_basis,
             n_rbf,
             activation,
             cutoff,
             dir_mp=False,
             cg_mp=False):
        super().__init__()

        # self.atom_embed = nn.Embedding(100, 36, padding_idx=0)
        # self.res_embed = nn.Embedding(30, 36, padding_idx=0)
        self.atom_embed = nn.Embedding(100, int(n_atom_basis/2), padding_idx=0)
        self.res_embed = nn.Embedding(30, int(n_atom_basis/2), padding_idx=0)
        
        # distance transform
        self.dist_embed = DistanceEmbed(n_rbf=n_rbf,
                                  cutoff=cutoff,
                                  feat_dim=n_atom_basis,
                                  dropout=0.0)

        self.message_blocks = nn.ModuleList(
            [EquiMessageBlock(feat_dim=n_atom_basis,
                          activation=activation,
                          n_rbf=n_rbf,
                          cutoff=cutoff,
                          dropout=0.0)
             for _ in range(n_conv)]
        )

        self.update_blocks = nn.ModuleList(
            [UpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(n_conv)]
        )

        self.cg_message_blocks = nn.ModuleList(
            [EquiMessageBlock(feat_dim=n_atom_basis,
                          activation=activation,
                          n_rbf=n_rbf,
                          cutoff=cutoff,
                          dropout=0.0)
             for _ in range(n_conv)]
        )

        self.cg_update_blocks = nn.ModuleList(
            [UpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(n_conv)]
        )

        self.cgmessage_layers = nn.ModuleList(
        [ContractiveMessageBlock(feat_dim=n_atom_basis,
                                         activation=activation,
                                         n_rbf=n_rbf,
                                         cutoff=20.0,
                                         dropout=0.0)
         for _ in range(n_conv)])
        
        self.atom2CGcouplings =nn.ModuleList( [ nn.Sequential(Dense(in_features=n_atom_basis,
                                                       out_features=n_atom_basis,
                                                       bias=True,
                                                       activation=to_module(activation)),
                                                 Dense(in_features=n_atom_basis,
                                                       out_features=n_atom_basis,
                                                       bias=True)) for _ in range(n_conv)])

        self.n_conv = n_conv
        self.dir_mp = dir_mp
        self.cg_mp = cg_mp
        self.n_atom_basis = n_atom_basis
    
    def forward(self, z, xyz, cg_z, cg_xyz, mapping, nbr_list, cg_nbr_list, ic):
        
        # atomic embedding
        if not self.dir_mp:
            nbr_list, _ = make_directed(nbr_list)
        cg_nbr_list, _ = make_directed(cg_nbr_list)
        
        h_atom = self.atom_embed(z.long())
        h_res = self.res_embed(cg_z[mapping].long())
        h = torch.cat([h_atom, h_res], axis=-1)

        # h = self.res_embed(cg_z[mapping].long())
        # h = torch.zeros(z.shape[0], 78).to(z.device)
        del z

        v = torch.zeros(h.shape[0], h.shape[1], 3).to(h.device)

        r_ij = xyz[nbr_list[:, 1]] - xyz[nbr_list[:, 0]]
        # r_ij = torch.zeros_like(r_ij).to(h.device)

        # r_IJ = cg_xyz[cg_nbr_list[:, 1]] - xyz[cg_nbr_list[:, 0]]
        
        # edge features
        r_iI = (xyz - cg_xyz[mapping])
        
        for i in range(self.n_conv):
            ds_message, dv_message = self.message_blocks[i](s_j=h,
                                                   v_j=v,
                                                   r_ij=r_ij,
                                                   nbrs=nbr_list)
            h = h + ds_message
            v = v + dv_message

            # contruct atom messages 
            if i == 0:
                H = scatter_mean(h, mapping, dim=0)
                V = scatter_mean(v, mapping, dim=0) 

            # CG message passing 
            dH, dV = self.cgmessage_layers[i](h, v, r_iI, mapping)

            H = H + dH
            V = V + dV
        
        return H, h


class CGprior(nn.Module):
    
    def __init__(self,
             n_conv,
             n_atom_basis,
             n_rbf,
             activation,
             cutoff,
             dir_mp=False):
        super().__init__()

        self.res_embed = nn.Embedding(30, n_atom_basis, padding_idx=0)
        # distance transform
        self.dist_embed = DistanceEmbed(n_rbf=n_rbf,
                                  cutoff=cutoff,
                                  feat_dim=n_atom_basis,
                                  dropout=0.0)

        self.message_blocks = nn.ModuleList(
            [EquiMessageBlock(feat_dim=n_atom_basis,
                          activation=activation,
                          n_rbf=n_rbf,
                          cutoff=cutoff,
                          dropout=0.0)
             for _ in range(n_conv)]
        )

        self.update_blocks = nn.ModuleList(
            [UpdateBlock(feat_dim=n_atom_basis,
                         activation=activation,
                         dropout=0.0)
             for _ in range(n_conv)]
        )

        self.mu = nn.Sequential(nn.Linear(n_atom_basis, n_atom_basis), nn.Tanh(), nn.Linear(n_atom_basis, n_atom_basis))
        self.sigma = nn.Sequential(nn.Linear(n_atom_basis, n_atom_basis), nn.Tanh(), nn.Linear(n_atom_basis, n_atom_basis))
        
        self.n_conv = n_conv
        self.dir_mp = dir_mp
    
    def forward(self, cg_z, cg_xyz, cg_nbr_list):
        
        # atomic embedding
        #if not self.dir_mp:
        cg_nbr_list, _ = make_directed(cg_nbr_list)

        h = self.res_embed(cg_z.long())
        v = torch.zeros(h.shape[0], h.shape[1], 3).to(h.device)

        r_ij = cg_xyz[cg_nbr_list[:, 1]] - cg_xyz[cg_nbr_list[:, 0]]

        for i in range(self.n_conv):
            ds_message, dv_message = self.message_blocks[i](s_j=h,
                                                   v_j=v,
                                                   r_ij=r_ij,
                                                   nbrs=cg_nbr_list)
            h = h + ds_message
            v = v + dv_message

            # # update block
            # ds_update, dv_update = self.update_blocks[i](s_i=h, v_i=v)
            # h = h + ds_update # atom message 
            # v = v + dv_update

        H_mu = self.mu(h)
        H_sigma = self.sigma(h)

        H_std = 1e-9 + torch.exp(H_sigma / 2)

        return H_mu, H_std


class CGequiVAE(nn.Module):
    def __init__(self, encoder, equivaraintconv, 
                     atom_munet, atom_sigmanet,
                     n_cgs, feature_dim,
                    prior_net=None, 
                    det=False, equivariant=True, offset=True):
        nn.Module.__init__(self)
        self.encoder = encoder
        self.equivaraintconv = equivaraintconv
        self.atom_munet = atom_munet
        self.atom_sigmanet = atom_sigmanet

        self.n_cgs = n_cgs
        self.prior_net = prior_net
        self.det = det

        self.offset = offset
        self.equivariant = equivariant
        if equivariant == False:
            self.euclidean = nn.Linear(self.encoder.n_atom_basis, self.encoder.n_atom_basis * 3)
        
    def get_inputs(self, batch):

        xyz = batch['nxyz'][:, 1:]

        cg_xyz = batch['CG_nxyz'][:, 1:]

        cg_z = batch['CG_nxyz'][:, 0]
        z = batch['nxyz'][:, 0]

        mapping = batch['CG_mapping']

        nbr_list = batch['nbr_list']
        CG_nbr_list = batch['CG_nbr_list']
        
        num_CGs = batch['num_CGs']
        
        return z, cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs
        
    def reparametrize(self, mu, sigma):
        eps = torch.randn_like(sigma)
        S_I = eps.mul(sigma).add_(mu)

        return S_I

    def CG2ChannelIdx(self, CG_mapping):

        CG2atomChannel = torch.zeros_like(CG_mapping)#.to("cpu")

        for cg_type in torch.unique(CG_mapping): 
            cg_filter = CG_mapping == cg_type
            num_contri_atoms = cg_filter.sum().item()
            CG2atomChannel[cg_filter] = torch.LongTensor(list(range(num_contri_atoms)))#.to(CG_mapping.device)

        return CG2atomChannel.detach()
            
    def decoder(self, cg_xyz, CG_nbr_list, S_I, s_i, mapping, num_CGs):
        cg_s, cg_v = self.equivaraintconv(cg_xyz, CG_nbr_list, mapping,S_I)

        CG2atomChannel = self.CG2ChannelIdx(mapping)
        
        # implement an non-equivariant decoder 
        if self.equivariant == False: 
            dv = self.euclidean(cg_s).reshape(cg_s.shape[0], cg_s.shape[1], 3)
            xyz_rel = dv[mapping, CG2atomChannel, :]
        else:
            xyz_rel = cg_v[mapping, CG2atomChannel, :]
            
        #this constraint is only true for geometrical mean
        # need to include weights 

        if self.offset:
          decode_offsets = scatter_mean(xyz_rel, mapping, dim=0)
          xyz_rel = xyz_rel - decode_offsets[mapping]

        xyz_recon = xyz_rel + cg_xyz[mapping]
        return xyz_recon
        
    def forward(self, batch):

        atomic_nums, cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs= self.get_inputs(batch)

        S_I, s_i = self.encoder(atomic_nums, xyz, cg_xyz, mapping, nbr_list, CG_nbr_list)

        # get prior based on CG conv 
        if self.prior_net:
            H_prior_mu, H_prior_sigma = self.prior_net(cg_z, cg_xyz, CG_nbr_list)
        else:
            H_prior_mu, H_prior_sigma = None, None 

        z = S_I

        mu = self.atom_munet(z)
        logvar = self.atom_sigmanet(z)
        sigma = 1e-12 + torch.exp(logvar / 2)
        

        if not self.det: 
            z_sample = self.reparametrize(mu, sigma)
        else:
            z_sample = z

        S_I = z_sample # s_i not used in decoding 
        xyz_recon = self.decoder(cg_xyz, CG_nbr_list, S_I, s_i, mapping, num_CGs)
        
        return mu, sigma, H_prior_mu, H_prior_sigma, xyz, xyz_recon


class internalCGequiVAE(nn.Module):
    def __init__(self, encoder, equivaraintconv, 
                     atom_munet, atom_sigmanet,
                     n_cgs, feature_dim,
                    prior_net=None, 
                    det=False, equivariant=True, offset=True):
        nn.Module.__init__(self)
        self.encoder = encoder
        self.equivaraintconv = equivaraintconv
        self.atom_munet = atom_munet
        self.atom_sigmanet = atom_sigmanet

        self.n_cgs = n_cgs
        self.prior_net = prior_net
        self.det = det

        self.offset = offset
        self.equivariant = equivariant
        if equivariant == False:
            self.euclidean = nn.Linear(self.encoder.n_atom_basis, self.encoder.n_atom_basis * 3)
        
    def get_inputs(self, batch):

        xyz = batch['nxyz'][:, 1:]

        cg_nxyz = batch['CG_nxyz']
        cg_xyz = batch['CG_nxyz'][:, 1:]
        cg_z = batch['CG_nxyz'][:, 0] # residue type
        
        z = batch['nxyz'][:, 0] # atom type

        mapping = batch['CG_mapping']

        nbr_list = batch['nbr_list']
        CG_nbr_list = batch['CG_nbr_list']
        
        num_CGs = batch['num_CGs']

        # Internal coordinates (ic) parameters
        ic = batch['ic']
        # ic_type = batch['ic_type']
        
        return z, cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs, ic, cg_nxyz
        
    def reparametrize(self, mu, sigma):
        eps = torch.randn_like(sigma)
        S_I = eps.mul(sigma).add_(mu)

        return S_I

    def CG2ChannelIdx(self, CG_mapping):

        CG2atomChannel = torch.zeros_like(CG_mapping).to("cpu")

        for cg_type in torch.unique(CG_mapping): 
            cg_filter = CG_mapping == cg_type
            num_contri_atoms = cg_filter.sum().item()
            CG2atomChannel[cg_filter] = torch.LongTensor(list(range(num_contri_atoms)))#.to(CG_mapping.device)

        return CG2atomChannel.detach()
            
    def decoder(self, cg_xyz, CG_nbr_list, mapping, S_I, mask):
        _, ic_recon = self.equivaraintconv(cg_xyz, CG_nbr_list, mapping, S_I, mask)
        
        return ic_recon
        
    def forward(self, batch):

        atomic_nums, cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs, ic, cg_nxyz = self.get_inputs(batch)
        S_I, s_i = self.encoder(atomic_nums, xyz, cg_z, cg_xyz, mapping, nbr_list, CG_nbr_list, ic)
        # mu, logvar = self.encoder(cg_z, cg_xyz, CG_nbr_list)

        # get prior based on CG conv 
        if self.prior_net:
            H_prior_mu, H_prior_sigma = self.prior_net(cg_z, cg_xyz, CG_nbr_list)
            # H_prior_mu, H_prior_sigma = torch.zeros_like(H_prior_mu).to(mu.device), torch.ones_like(H_prior_sigma).to(mu.device)
        else:
            H_prior_mu, H_prior_sigma = None, None 
        
        z = S_I

        mu = self.atom_munet(z)
        logvar = self.atom_sigmanet(z)
        sigma = 1e-12 + torch.exp(logvar / 2)

        print("encoder m", mu.mean(), mu.var())
        print("prior m", H_prior_mu.mean(), H_prior_mu.var())
        print("encoder e", sigma.mean(), sigma.var())
        print("prior e", H_prior_sigma.mean(), H_prior_sigma.var())
        # change 0
        # self.det = True
        if not self.det: 
            z_sample = self.reparametrize(mu, sigma)
        else:
            z_sample = z

        S_I = z_sample # s_i not used in decoding 
        # S_I = torch.zeros_like(z_sample).to(z.device)

        # mask = torch.cat([batch['mask']])
        # ic_recon = self.decoder(cg_nxyz, CG_nbr_list, S_I, s_i, mapping, mask)
        ic_recon = self.decoder(cg_xyz, CG_nbr_list, mapping, S_I, mask=None)
        
        return mu, sigma, H_prior_mu, H_prior_sigma, ic, ic_recon


class multiCGequiVAE(nn.Module):
    def __init__(self, encoder, equivaraintconv, 
                     atom_munet, atom_sigmanet,
                     n_cgs, feature_dim,
                    prior_net=None, 
                    det=False, equivariant=True, offset=True):
        nn.Module.__init__(self)
        self.encoder = encoder
        self.equivaraintconv = equivaraintconv
        self.atom_munet = atom_munet
        self.atom_sigmanet = atom_sigmanet

        self.n_cgs = n_cgs
        self.prior_net = prior_net
        self.det = det

        self.offset = offset
        self.equivariant = equivariant
        if equivariant == False:
            self.euclidean = nn.Linear(self.encoder.n_atom_basis, self.encoder.n_atom_basis * 3)
        
    def get_inputs(self, batch):

        xyz = batch['nxyz'][:, 1:]

        cg_xyz = batch['CG_nxyz'][:, 1:]

        cg_z = batch['CG_nxyz'][:, 0] # residue type
        z = batch['nxyz'][:, 0]

        mapping = batch['CG_mapping']

        nbr_list = batch['nbr_list']
        CG_nbr_list = batch['CG_nbr_list']
        
        num_CGs = batch['num_CGs']
        
        return z, cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs
        
    def reparametrize(self, mu, sigma):
        eps = torch.randn_like(sigma)
        S_I = eps.mul(sigma).add_(mu)

        return S_I

    def CG2ChannelIdx(self, CG_mapping):

        CG2atomChannel = torch.zeros_like(CG_mapping).to("cpu")

        for cg_type in torch.unique(CG_mapping): 
            cg_filter = CG_mapping == cg_type
            num_contri_atoms = cg_filter.sum().item()
            CG2atomChannel[cg_filter] = torch.LongTensor(list(range(num_contri_atoms)))#.to(CG_mapping.device)

        return CG2atomChannel.detach()
            
    def decoder(self, cg_xyz, CG_nbr_list, S_I, s_i, mapping, num_CGs):
        cg_s, cg_v = self.equivaraintconv(cg_xyz, CG_nbr_list, mapping,S_I)

        CG2atomChannel = self.CG2ChannelIdx(mapping)
        
        # implement an non-equivariant decoder 
        if self.equivariant == False: 
            dv = self.euclidean(cg_s).reshape(cg_s.shape[0], cg_s.shape[1], 3)
            xyz_rel = dv[mapping, CG2atomChannel, :]
        else:
            xyz_rel = cg_v[mapping, CG2atomChannel, :]
        
        #this constraint is only true for geometrical mean
        # need to include weights 

        if self.offset:
          decode_offsets = scatter_mean(xyz_rel, mapping, dim=0)
          xyz_rel = xyz_rel - decode_offsets[mapping]

        xyz_recon = xyz_rel + cg_xyz[mapping]
        return xyz_recon
        
    def forward(self, batch):

        atomic_nums, cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs= self.get_inputs(batch)
        # z, cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs

        S_I, s_i = self.encoder(atomic_nums, xyz, cg_xyz, mapping, nbr_list, CG_nbr_list)

        # get prior based on CG conv 
        if self.prior_net:
            H_prior_mu, H_prior_sigma = self.prior_net(cg_z, cg_xyz, CG_nbr_list)
        else:
            H_prior_mu, H_prior_sigma = None, None 
        
        z = S_I

        mu = self.atom_munet(z)
        logvar = self.atom_sigmanet(z)
        sigma = 1e-12 + torch.exp(logvar / 2)

        if not self.det: 
            z_sample = self.reparametrize(mu, sigma)
        else:
            z_sample = z

        S_I = z_sample # s_i not used in decoding 
        xyz_recon = self.decoder(cg_xyz, CG_nbr_list, S_I, s_i, mapping, num_CGs)
        
        return mu, sigma, H_prior_mu, H_prior_sigma, xyz, xyz_recon
    
class PCN(nn.Module):
    '''Protein Completion Networks'''
    def __init__(self, equivaraintconv, feature_dim, offset=True):
        nn.Module.__init__(self)

        self.equivaraintconv = equivaraintconv
        self.offset = offset
        self.embedding = nn.Embedding(100, feature_dim, padding_idx=0)
        
    def get_inputs(self, batch):

        xyz = batch['xyz']
        cg_xyz = batch['ca_xyz']
        cg_z = batch['res']
        mapping = batch['cg_map']
        #dihe = batch['dihe_idxs']
        nbr_list = batch['bond_edge_list']
        CG_nbr_list = batch['CG_nbr_list']
        num_CGs = [len(seq) for seq in batch['seq']] 
        
        return cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs
        
    def CG2ChannelIdx(self, CG_mapping):

        CG2atomChannel = torch.zeros_like(CG_mapping)#.to("cpu")

        for cg_type in torch.unique(CG_mapping): 
            cg_filter = CG_mapping == cg_type
            num_contri_atoms = cg_filter.sum().item()
            CG2atomChannel[cg_filter] = torch.LongTensor(list(range(num_contri_atoms)))#.to(CG_mapping.device)
            
        return CG2atomChannel.detach()
            
    def decoder(self, cg_xyz, CG_nbr_list, S_I, ca_idx, mapping, num_CGs):
        
        cg_s, cg_v = self.equivaraintconv(cg_xyz, CG_nbr_list, mapping, S_I)

        CG2atomChannel = self.CG2ChannelIdx(mapping)

        # implement an non-equivariant decoder 
        xyz_rel = cg_v[mapping, CG2atomChannel, :]

        #this constraint is only true for geometrical mean
        # need to include weights 

        # if self.offset:
        #   decode_offsets = scatter_mean(xyz_rel, mapping, dim=0)
        #   xyz_rel = xyz_rel - decode_offsets[mapping]

        # recentering 
        #ca_idx = batch['ca_idx'] #self.get_ca_idx(mapping)

        # edge case for some weird data
        if ca_idx[-1].item() < xyz_rel.shape[0]:
            offset = torch.clone( xyz_rel[ca_idx] ) 
            xyz_rel[ca_idx] -= offset 

        # reconstruct coordinates 
        xyz_recon = xyz_rel + cg_xyz[mapping]

        return xyz_recon

    # def get_ca_idx(self, mapping):
    #     ca_idx = [1]
    #     current = 0
    #     for i, item in enumerate(mapping):
    #         if item.item() != current:
    #             ca_idx.append(i + 1)
    #         current = item.item()

    #     return torch.LongTensor(ca_idx)
        
    def forward(self, batch):
        cg_z, xyz, cg_xyz, nbr_list, CG_nbr_list, mapping, num_CGs = self.get_inputs(batch)

        S_I = self.embedding(cg_z.to(torch.long))
        xyz_recon = self.decoder(cg_xyz, CG_nbr_list, S_I, batch['ca_idx'], mapping, num_CGs)

        return None, None, None, None, xyz, xyz_recon