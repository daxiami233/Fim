import { Stmt, ArkMethod, FileSignature, Scene } from "../../../../arkanalyzer/src";
import { PageTransitionGraph, PTGNode } from "../../PageTransitionGraph";
import { NodeBuilderInterface } from "./BasicNodeBuilder";
import Const from "../../../common/Constant";
import fs from "fs";
import Utils from "../../../common/Utils";

export class RouterMapNodeBuilder implements NodeBuilderInterface{
    nodeBuilderStrategy: string = "RouterMapNodeBuilder";
    scene: Scene;
    ptg:PageTransitionGraph;

    constructor(scene: Scene, ptg: PageTransitionGraph){
        this.scene = scene;
        this.ptg = ptg;
    }

    public identifyPageNodes(){
        const routerMapFile = this.scene.getRealProjectDir() + Const.ROUTERMAPFILE;
        const routerMapText = fs.readFileSync(routerMapFile, 'utf-8');
        let routerMap = JSON.parse(routerMapText).routerMap;
        // 提取 name 和 pageSourceFile，并组合成键值对
        const result = routerMap.reduce((acc:any, item:any) => {
            // 提取文件名（去掉路径前缀）
            const fileName = item.pageSourceFile.split('/').pop() || item.pageSourceFile;
            acc[item.name] = "pages/"+fileName.replace('.ets', '');
            return acc;
        }, {} as Record<string, string>);

        for (const key in result) {
            if (result.hasOwnProperty(key)) {
                const value = result[key];
                // console.log(`${key}: ${value}`);
                // let clazz = Utils.getComponentClassOfPage(this.scene, value);
                // if(clazz != undefined){
                //     let viewTree = clazz?.getViewTree();
                //     // ptgNodes.push
                //     this.ptg.addPTGNode(value, '',  clazz, viewTree, key);
                // }
            }
        }
    }

    
        
    
}