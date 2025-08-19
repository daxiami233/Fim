import { Stmt, ArkMethod, FileSignature, Scene } from "../../../../arkanalyzer/src";
import { PageTransitionGraph, PTGNode } from "../../PageTransitionGraph";
import Const from "../../../common/Constant";
import fs from "fs";
import path from 'path';
import * as JSON5 from "json5";
import Utils from "../../../common/Utils";
import { NodeBuilderInterface } from "./BasicNodeBuilder";
import { moveSyntheticComments } from "ohos-typescript";

export class NodeBuilder implements NodeBuilderInterface {
    nodeBuilderStrategy: string = "NodeBuilder";
    scene: Scene;
    ptg:PageTransitionGraph;

    constructor(scene: Scene, ptg: PageTransitionGraph) {
        this.scene = scene;
        this.ptg = ptg;
    }

    private identifyPageNodesByPages(pagesSig: string, moduleName: string, modulePath: string) {
        const pagesJson = Utils.getJsonFile(modulePath, pagesSig);
        const pages = pagesJson.src;
        for (const page of pages) {
            const pagePath = `${Const.ETS_DIR}/${page}.ets`
            let clazz = Utils.getComponentClassOfPage(this.scene, moduleName, pagePath);
            if(clazz != undefined){
                let viewTree = clazz?.getViewTree();
                this.ptg.addPTGNode(moduleName, pagePath, clazz, viewTree, Const.DEFAULT_NAME);
            }
        }
    }

    private identifyPageNodesByRouteMap(routeMapSig: string, moduleName: string, modulePath: string) {
        const routeMapJson = Utils.getJsonFile(modulePath, routeMapSig);
        const pages = routeMapJson.routerMap;
        for (const page of pages) {
            const pagePath = page.pageSourceFile;
            const pageName = page.name;
            const id = this.ptg.getPathToPTGNodeMap().get(pagePath);
            if (id != undefined) {
                const node = this.ptg.getNode(id) as PTGNode;
                node.setPageAlias(pageName);
            } else {
                let clazz = Utils.getComponentClassOfPage(this.scene, moduleName, pagePath);
                if(clazz != undefined){
                    let viewTree = clazz?.getViewTree();
                    this.ptg.addPTGNode(moduleName, pagePath, clazz, viewTree, pageName);
                }
            }
        }
    }

    public identifyPageNodes() {
        for (const [name, moduleScene] of this.scene.getModuleSceneMap()) {
            const modulePath = moduleScene.getModulePath();
            const moduleJson5Path = path.join(modulePath, Const.MODULE_JSON5);
            console.log(moduleJson5Path);
            if (fs.existsSync(moduleJson5Path)) {
                let moduleText: string;
                try {
                    moduleText = fs.readFileSync(moduleJson5Path, 'utf-8');
                } catch (error) {
                    console.log(`Error reading file: ${error}`);
                    return;
                }
                const moduleJson = JSON5.parse(moduleText);
                const pagesSig = moduleJson.module.pages;
                const routerMapSig = moduleJson.module.routerMap;
                if (pagesSig != undefined)
                    this.identifyPageNodesByPages(pagesSig, name, modulePath);
                if (routerMapSig != undefined)
                    this.identifyPageNodesByRouteMap(routerMapSig, name, modulePath);
            } else {
            console.log('There is no module.json5 for this project.');
            }
        }
        
        // const mainPagesFile =this.scene.getRealProjectDir() +Const.MAINPAGEFILES;
        // const mainPagesText = fs.readFileSync(mainPagesFile, 'utf-8');
        // const pages = JSON.parse(mainPagesText).src;

        // for (const page of pages) {
        //     let clazz = Utils.getComponentClassOfPage(this.scene, page);
        //     if(clazz != undefined){
        //         let viewTree = clazz?.getViewTree();
        //         // ptgNodes.push
        //         this.ptg.addPTGNode(page, clazz, viewTree);
        //     }
        // }
    }

    
        
    
}