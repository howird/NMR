from __future__ import division
import math

import torch
import torch.nn as nn
import numpy

import neural_renderer as nr


class Renderer(nn.Module):
    def __init__(
        self,
        image_size=256,
        anti_aliasing=True,
        background_color=[0, 0, 0],
        fill_back=True,
        camera_mode="projection",
        K=None,
        R=None,
        t=None,
        dist_coeffs=None,
        orig_size=1024,
        perspective=True,
        viewing_angle=30,
        camera_direction=[0, 0, 1],
        near=0.1,
        far=100,
        light_intensity_ambient=0.5,
        light_intensity_directional=0.5,
        light_color_ambient=[1, 1, 1],
        light_color_directional=[1, 1, 1],
        light_direction=[0, 1, 0],
    ):
        super(Renderer, self).__init__()
        # rendering
        self.image_size = image_size
        self.anti_aliasing = anti_aliasing
        self.background_color = background_color
        self.fill_back = fill_back

        # camera
        self.camera_mode = camera_mode
        if self.camera_mode == "projection":
            if isinstance(K, numpy.ndarray):
                K = torch.tensor(K, dtype=torch.float32)
            if isinstance(R, numpy.ndarray):
                R = torch.tensor(R, dtype=torch.float32)
            if isinstance(t, numpy.ndarray):
                t = torch.tensor(t, dtype=torch.float32)
            if dist_coeffs is None:
                dist_coeffs = torch.tensor(
                    [[0.0, 0.0, 0.0, 0.0, 0.0]], dtype=torch.float32
                )
            # Register buffers to make them persistent
            self.register_buffer("K", K)
            self.register_buffer("R", R)
            self.register_buffer("t", t)
            self.register_buffer("dist_coeffs", dist_coeffs)

            self.orig_size = orig_size
        elif self.camera_mode in ["look", "look_at"]:
            self.perspective = perspective
            self.viewing_angle = viewing_angle
            self.eye = [0, 0, -(1.0 / math.tan(math.radians(self.viewing_angle)) + 1)]
            self.camera_direction = [0, 0, 1]
        else:
            raise ValueError("Camera mode has to be one of projection, look or look_at")

        self.near = near
        self.far = far

        # light
        self.light_intensity_ambient = light_intensity_ambient
        self.light_intensity_directional = light_intensity_directional
        self.light_color_ambient = light_color_ambient
        self.light_color_directional = light_color_directional
        self.light_direction = light_direction

        # rasterization
        self.rasterizer_eps = 1e-3

    def forward(
        self,
        vertices,
        faces,
        textures=None,
        mode=None,
        K=None,
        R=None,
        t=None,
        dist_coeffs=None,
        orig_size=None,
    ):
        """
        Implementation of forward rendering method
        The old API is preserved for back-compatibility with the Chainer implementation
        """

        if mode is None:
            return self.render(
                vertices, faces, textures, K, R, t, dist_coeffs, orig_size
            )
        elif mode is "rgb":
            return self.render_rgb(
                vertices, faces, textures, K, R, t, dist_coeffs, orig_size
            )
        elif mode == "silhouettes":
            return self.render_silhouettes(
                vertices, faces, K, R, t, dist_coeffs, orig_size
            )
        elif mode == "depth":
            return self.render_depth(vertices, faces, K, R, t, dist_coeffs, orig_size)
        elif mode is "visibility":
            return self.visibility(vertices, faces, K, R, t, dist_coeffs, orig_size)
        else:
            raise ValueError("mode should be one of None, 'silhouettes' or 'depth'")

    def visibility(
        self, vertices, faces, K=None, R=None, t=None, dist_coeffs=None, orig_size=None
    ):
        # fill back
        if self.fill_back:
            faces = torch.cat(
                (faces, faces[:, :, list(reversed(range(faces.shape[-1])))]), dim=1
            )

        # viewpoint transformation
        if self.camera_mode == "look_at":
            vertices = nr.look_at(vertices, self.eye)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "look":
            vertices = nr.look(vertices, self.eye, self.camera_direction)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "projection":
            if K is None:
                K = self.K
            if R is None:
                R = self.R
            if t is None:
                t = self.t
            if dist_coeffs is None:
                dist_coeffs = self.dist_coeffs
            if orig_size is None:
                orig_size = self.orig_size
            vertices = nr.projection(vertices, K, R, t, dist_coeffs, orig_size)

        # rasterization
        faces = nr.vertices_to_faces(vertices, faces)
        face_visibility = nr.face_visibility(
            faces, self.image_size, near=self.near, far=self.far
        )
        return face_visibility

    def render_silhouettes(
        self, vertices, faces, K=None, R=None, t=None, dist_coeffs=None, orig_size=None
    ):
        # fill back
        if self.fill_back:
            faces = torch.cat(
                (faces, faces[:, :, list(reversed(range(faces.shape[-1])))]), dim=1
            )

        # viewpoint transformation
        if self.camera_mode == "look_at":
            vertices = nr.look_at(vertices, self.eye)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "look":
            vertices = nr.look(vertices, self.eye, self.camera_direction)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "projection":
            if K is None:
                K = self.K
            if R is None:
                R = self.R
            if t is None:
                t = self.t
            if dist_coeffs is None:
                dist_coeffs = self.dist_coeffs
            if orig_size is None:
                orig_size = self.orig_size
            vertices = nr.projection(vertices, K, R, t, dist_coeffs, orig_size)

        # rasterization
        faces = nr.vertices_to_faces(vertices, faces)
        images = nr.rasterize_silhouettes(faces, self.image_size, self.anti_aliasing)
        return images

    def render_depth(
        self, vertices, faces, K=None, R=None, t=None, dist_coeffs=None, orig_size=None
    ):
        # fill back
        if self.fill_back:
            faces = torch.cat(
                (faces, faces[:, :, list(reversed(range(faces.shape[-1])))]), dim=1
            ).detach()

        # viewpoint transformation
        if self.camera_mode == "look_at":
            vertices = nr.look_at(vertices, self.eye)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "look":
            vertices = nr.look(vertices, self.eye, self.camera_direction)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "projection":
            if K is None:
                K = self.K
            if R is None:
                R = self.R
            if t is None:
                t = self.t
            if dist_coeffs is None:
                dist_coeffs = self.dist_coeffs
            if orig_size is None:
                orig_size = self.orig_size
            vertices = nr.projection(vertices, K, R, t, dist_coeffs, orig_size)

        # rasterization
        faces = nr.vertices_to_faces(vertices, faces)
        images = nr.rasterize_depth(faces, self.image_size, self.anti_aliasing)
        return images

    def render_rgb(
        self,
        vertices,
        faces,
        textures,
        K=None,
        R=None,
        t=None,
        dist_coeffs=None,
        orig_size=None,
    ):
        # fill back
        if self.fill_back:
            faces = torch.cat(
                (faces, faces[:, :, list(reversed(range(faces.shape[-1])))]), dim=1
            ).detach()
            textures = torch.cat(
                (textures, textures.permute((0, 1, 4, 3, 2, 5))), dim=1
            )

        # lighting
        faces_lighting = nr.vertices_to_faces(vertices, faces)
        textures = nr.lighting(
            faces_lighting,
            textures,
            self.light_intensity_ambient,
            self.light_intensity_directional,
            self.light_color_ambient,
            self.light_color_directional,
            self.light_direction,
        )

        # viewpoint transformation
        if self.camera_mode == "look_at":
            vertices = nr.look_at(vertices, self.eye)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "look":
            vertices = nr.look(vertices, self.eye, self.camera_direction)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "projection":
            if K is None:
                K = self.K
            if R is None:
                R = self.R
            if t is None:
                t = self.t
            if dist_coeffs is None:
                dist_coeffs = self.dist_coeffs
            if orig_size is None:
                orig_size = self.orig_size
            vertices = nr.projection(vertices, K, R, t, dist_coeffs, orig_size)

        # rasterization
        faces = nr.vertices_to_faces(vertices, faces)
        images = nr.rasterize(
            faces,
            textures,
            self.image_size,
            self.anti_aliasing,
            self.near,
            self.far,
            self.rasterizer_eps,
            self.background_color,
        )
        return images

    def render(
        self,
        vertices,
        faces,
        textures,
        K=None,
        R=None,
        t=None,
        dist_coeffs=None,
        orig_size=None,
    ):
        # fill back
        if self.fill_back:
            faces = torch.cat(
                (faces, faces[:, :, list(reversed(range(faces.shape[-1])))]), dim=1
            ).detach()
            textures = torch.cat(
                (textures, textures.permute((0, 1, 4, 3, 2, 5))), dim=1
            )

        # lighting
        faces_lighting = nr.vertices_to_faces(vertices, faces)
        textures = nr.lighting(
            faces_lighting,
            textures,
            self.light_intensity_ambient,
            self.light_intensity_directional,
            self.light_color_ambient,
            self.light_color_directional,
            self.light_direction,
        )

        # viewpoint transformation
        if self.camera_mode == "look_at":
            vertices = nr.look_at(vertices, self.eye)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "look":
            vertices = nr.look(vertices, self.eye, self.camera_direction)
            # perspective transformation
            if self.perspective:
                vertices = nr.perspective(vertices, angle=self.viewing_angle)
        elif self.camera_mode == "projection":
            if K is None:
                K = self.K
            if R is None:
                R = self.R
            if t is None:
                t = self.t
            if dist_coeffs is None:
                dist_coeffs = self.dist_coeffs
            if orig_size is None:
                orig_size = self.orig_size
            vertices = nr.projection(vertices, K, R, t, dist_coeffs, orig_size)

        # rasterization
        faces = nr.vertices_to_faces(vertices, faces)
        out = nr.rasterize_rgbad(
            faces,
            textures,
            self.image_size,
            self.anti_aliasing,
            self.near,
            self.far,
            self.rasterizer_eps,
            self.background_color,
        )
        return out["rgb"], out["depth"], out["alpha"]
